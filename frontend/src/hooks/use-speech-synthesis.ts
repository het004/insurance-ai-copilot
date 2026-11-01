"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SPEECH_LANG } from "@/lib/utils";
import { api } from "@/services/api";

const ARABIC = /[؀-ۿ]+/g;

export function isArabicText(text: string): boolean {
  const ar = (text.match(/[\u0600-\u06FF]/g) || []).length;
  const en = (text.match(/[A-Za-z]/g) || []).length;
  return ar > 0 && ar >= en * 0.6;
}

/** Turn markdown + symbols into something that sounds natural when spoken. */
export function toSpeech(text: string, keepArabic = true): string {
  let s = text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/\[(\d+)\]/g, "")                         // citation markers
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")             // links
    .replace(/[*_#>`|]/g, "")
    .replace(/SAR\s?([\d,]+(?:\.\d+)?)M\b/g, "$1 million riyals")
    .replace(/SAR\s?([\d,]+(?:\.\d+)?)/g, "$1 riyals")
    .replace(/\bNCD\b/g, "No Claim Discount")
    .replace(/\bTPL\b/g, "T P L")
    .replace(/\bVAT\b/g, "V A T")
    .replace(/\bPOL-[A-Z]+-\d*(\d{4})\b/g, (_, d) => `ending ${d.split("").join(" ")}`)
    .replace(/\bCLM-(\d{4})-(\d{4})/g, (_, a, b) => `C L M ${a.split("").join(" ")}, ${b.split("").join(" ")}`)
    .replace(/\b(\d{4}) ([A-Z]{3})\b/g, (_, n, l) => `${n.split("").join(" ")} ${l.split("").join(" ")}`) // plates
    .replace(/\s*\n+\s*-\s*/g, ". ")
    .replace(/—/g, ", ");
  if (!keepArabic) s = s.replace(ARABIC, " ");
  return s.replace(/\s+/g, " ").trim();
}

function chunk(text: string, max = 180): string[] {
  const sentences = text.match(/[^.!?]+[.!?]*/g) || [text];
  const out: string[] = [];
  let buf = "";
  for (const s of sentences) {
    if ((buf + s).length > max && buf) {
      out.push(buf.trim());
      buf = "";
    }
    buf += s;
  }
  if (buf.trim()) out.push(buf.trim());
  return out;
}

/** Rank browser voices: Edge "Natural"/"Online" neural voices first, then Google, then the OS default. */
function pickBrowserVoice(voices: SpeechSynthesisVoice[], lang: string): SpeechSynthesisVoice | null {
  const base = lang.split("-")[0];
  const score = (v: SpeechSynthesisVoice) => {
    let s = 0;
    if (v.lang === lang) s += 40;
    else if (v.lang.startsWith(base)) s += 25;
    else return -1;
    if (/natural|neural/i.test(v.name)) s += 30;
    if (/online/i.test(v.name)) s += 10;
    if (/google/i.test(v.name)) s += 12;
    if (/ava|emma|jenny|aria|samantha|zariyah|hamed/i.test(v.name)) s += 5;
    if (/desktop|espeak|compact/i.test(v.name)) s -= 15;
    return s;
  };
  return voices.map((v) => [score(v), v] as const).filter(([s]) => s >= 0).sort((a, b) => b[0] - a[0])[0]?.[1] ?? null;
}

/**
 * Speaks replies with a natural neural voice from the backend (/api/tts). If that isn't reachable it falls back
 * to the best voice the browser has, and remembers the fallback for the rest of the session.
 */
export function useSpeechSynthesis(lang = SPEECH_LANG) {
  const [supported, setSupported] = useState(false);
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const [engine, setEngine] = useState<"neural" | "browser">("neural");
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const neuralOk = useRef(true);
  const runRef = useRef(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setSupported(true);
    if (!("speechSynthesis" in window)) return;
    const pick = () => { voicesRef.current = window.speechSynthesis.getVoices(); };
    pick();
    window.speechSynthesis.addEventListener("voiceschanged", pick);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", pick);
      window.speechSynthesis.cancel();
    };
  }, [lang]);

  const stop = useCallback(() => {
    runRef.current++;
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
    }
    setSpeakingId(null);
  }, []);

  const speakBrowser = useCallback((text: string, run: number) => {
    if (!("speechSynthesis" in window)) {
      setSpeakingId(null);
      return;
    }
    const synth = window.speechSynthesis;
    synth.cancel();
    const arabic = isArabicText(text);
    const vLang = arabic ? "ar-SA" : lang.startsWith("ar") ? "en-US" : lang;
    const voice = pickBrowserVoice(voicesRef.current.length ? voicesRef.current : synth.getVoices(), vLang);
    // Chrome stops long utterances after ~15s, so speak sentence chunks
    const parts = chunk(toSpeech(text, arabic));
    if (!parts.length) return setSpeakingId(null);
    parts.forEach((p, i) => {
      const u = new SpeechSynthesisUtterance(p);
      u.lang = voice?.lang || vLang;
      if (voice) u.voice = voice;
      u.rate = 1.0;
      u.pitch = 1.02;
      if (i === parts.length - 1) u.onend = () => run === runRef.current && setSpeakingId(null);
      u.onerror = () => run === runRef.current && setSpeakingId(null);
      synth.speak(u);
    });
  }, [lang]);

  const speak = useCallback(
    (text: string, id = "current") => {
      if (typeof window === "undefined") return;
      stop();
      const run = ++runRef.current;
      setSpeakingId(id);
      if (!neuralOk.current) return speakBrowser(text, run);
      api.tts(toSpeech(text, true), isArabicText(text) ? "ar-SA" : "en-US")
        .then((blob) => {
          if (run !== runRef.current) return;
          const url = URL.createObjectURL(blob);
          const audio = audioRef.current ?? new Audio();
          audioRef.current = audio;
          audio.src = url;
          audio.onended = () => { URL.revokeObjectURL(url); if (run === runRef.current) setSpeakingId(null); };
          audio.onerror = () => { if (run === runRef.current) speakBrowser(text, run); };
          return audio.play().catch(() => speakBrowser(text, run)); // autoplay blocked → browser voice
        })
        .catch(() => {
          neuralOk.current = false; // backend can't reach the neural voice service — stop trying this session
          setEngine("browser");
          if (run === runRef.current) speakBrowser(text, run);
        });
    },
    [lang, speakBrowser, stop],
  );

  return { supported, speaking: speakingId !== null, speakingId, speak, stop, engine };
}
