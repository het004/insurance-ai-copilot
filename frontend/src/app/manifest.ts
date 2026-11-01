import type { MetadataRoute } from "next";
import { ASSISTANT_NAME, INSURER_NAME, INSURER_SHORT } from "@/lib/brand";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: `${INSURER_NAME} · AI Copilot`,
    short_name: INSURER_SHORT,
    description: `${ASSISTANT_NAME} — buy, claim and renew by voice`,
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#ffffff",
    theme_color: "#22447d",
    categories: ["finance", "productivity"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Talk to Copilot", url: "/chat?voice=1" },
      { name: "Get a quote", url: "/chat?q=I%20want%20a%20quote" },
      { name: "Report a claim", url: "/chat?q=I%20want%20to%20report%20a%20claim" },
    ],
  };
}
