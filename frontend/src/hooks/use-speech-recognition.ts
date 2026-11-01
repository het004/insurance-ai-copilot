"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SPEECH_LANG } from "@/lib/utils";
import { api } from "@/services/api";

/** Set when the server recogniser (Google Cloud Chirp) failed — the browser recogniser is used from then on. */
let serverSttFailed = false;

/* Minimal typings for the Web Speech API (not in every TS lib.dom version). */
interface SRAlternative { transcript: string; confidence: number }
interface SRResult { isFinal: boolean; length: number; [i: number]: SRAlternative }
interface SREvent { resultIndex: number; results: { length: number; [i: number]: SRResult } }
interface SRErrorEvent { error: string }
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onresult: ((e: SREvent) => void) | null;
  onerror: ((e: SRErrorEvent) => void) | null;
}
type SRCtor = new () => SpeechRecognitionLike;

function getCtor(): SRCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

const ERRORS: Record<string, string> = {
  "not-allowed": "Microphone access was blocked. Allow the mic in your browser's site settings and try again.",
  "service-not-allowed": "Speech recognition is disabled in this browser. Try Chrome, Edge or Safari.",
  "no-speech": "I didn't hear anything — tap the mic and try again.",
  "audio-capture": "No microphone was found on this device.",
  network: "Speech recognition needs an internet connection in this browser.",
};

let permissionPrimed = false;

/** Ask for mic permission once with getUserMedia so the browser prompt appears predictably. */
async function ensureMicPermission(): Promise<boolean> {
  if (permissionPrimed || typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) return true;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((t) => t.stop());
    permissionPrimed = true;
    return true;
  } catch {
    return false;
  }
}

/**
 * Voice input. With `server: true` the clip is recorded in the browser and transcribed by Google Cloud
 * Speech-to-Text (Chirp) on the backend — better accuracy, English and Saudi Arabic. Otherwise (or if that fails)
 * the browser's own SpeechRecognition is used.
 */
export function useSpeechRecognition(opts: { onFinal?: (text: string) => void; lang?: string; server?: boolean } = {}) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const mediaRef = useRef<{ stop: () => void } | null>(null);
  const onFinalRef = useRef(opts.onFinal);
  onFinalRef.current = opts.onFinal;
  const lang = opts.lang || SPEECH_LANG;

  const useServer = !!opts.server && !serverSttFailed;

  useEffect(() => {
    setSupported(!!getCtor() || (!!opts.server && typeof MediaRecorder !== "undefined"));
    return () => { recRef.current?.abort(); mediaRef.current?.stop(); };
  }, [opts.server]);

  /** Record until ~1.2 s of silence after speech (max 15 s), then send the clip for transcription. */
  const startServer = useCallback(async () => {
    if (mediaRef.current) return;
    window.speechSynthesis?.cancel();
    setError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      setError(ERRORS["not-allowed"]);
      return;
    }
    const mime = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm"].find((m) => MediaRecorder.isTypeSupported(m)) || "";
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const chunks: BlobPart[] = [];
    const ctx = new AudioContext();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const buf = new Float32Array(analyser.fftSize);
    const t0 = performance.now();
    let heard = false;
    let lastLoud = t0;
    let raf = 0;
    const finish = () => {
      cancelAnimationFrame(raf);
      if (rec.state !== "inactive") rec.stop();
    };
    const tick = () => {
      analyser.getFloatTimeDomainData(buf);
      const rms = Math.sqrt(buf.reduce((a, v) => a + v * v, 0) / buf.length);
      const now = performance.now();
      if (rms > 0.02) { heard = true; lastLoud = now; }
      if ((heard && now - lastLoud > 1200) || now - t0 > 15000 || (!heard && now - t0 > 7000)) return finish();
      raf = requestAnimationFrame(tick);
    };
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      ctx.close().catch(() => {});
      mediaRef.current = null;
      setListening(false);
      if (!heard) {
        setError(ERRORS["no-speech"]);
        setTranscript("");
        return;
      }
      setTranscript("Transcribing…");
      try {
        const r = await api.stt(new Blob(chunks, { type: rec.mimeType || "audio/webm" }), lang.startsWith("ar") ? "ar" : "en");
        setTranscript("");
        if (r.text) onFinalRef.current?.(r.text);
        else setError(ERRORS["no-speech"]);
      } catch {
        serverSttFailed = true; // fall back to the browser recogniser from now on
        setTranscript("");
        setError("Couldn't transcribe that — please tap the mic and say it again.");
      }
    };
    mediaRef.current = { stop: finish };
    rec.start(250);
    setListening(true);
    setTranscript("");
    raf = requestAnimationFrame(tick);
  }, [lang]);

  const start = useCallback(async () => {
    if (useServer && typeof MediaRecorder !== "undefined") return startServer();
    const Ctor = getCtor();
    if (!Ctor) {
      setError("Voice input isn't supported in this browser. Please use Chrome, Edge or Safari.");
      return;
    }
    if (recRef.current) return;
    window.speechSynthesis?.cancel(); // never listen while talking
    setError(null);
    if (!(await ensureMicPermission())) {
      setError(ERRORS["not-allowed"]);
      return;
    }
    const rec = new Ctor();
    rec.lang = lang;
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    let finalText = "";
    rec.onstart = () => {
      setListening(true);
      setTranscript("");
    };
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else interim += r[0].transcript;
      }
      setTranscript(`${finalText} ${interim}`.trim());
    };
    rec.onerror = (e) => {
      if (e.error !== "aborted") setError(ERRORS[e.error] || `Voice error: ${e.error}`);
    };
    rec.onend = () => {
      recRef.current = null;
      setListening(false);
      const text = finalText.trim();
      if (text) onFinalRef.current?.(text);
      setTranscript("");
    };
    recRef.current = rec;
    try {
      rec.start();
    } catch (err) {
      recRef.current = null;
      setError(String(err));
    }
  }, [lang, useServer, startServer]);

  const stop = useCallback(() => { recRef.current?.stop(); mediaRef.current?.stop(); }, []);
  const toggle = useCallback(() => (recRef.current || mediaRef.current ? stop() : start()), [start, stop]);

  return { supported, listening, transcript, error, start, stop, toggle, clearError: () => setError(null) };
}
