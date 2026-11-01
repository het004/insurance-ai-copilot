import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ASSISTANT_NAME, INSURER_NAME } from "@/lib/brand";

export const metadata: Metadata = {
  title: { default: `${INSURER_NAME} · ${ASSISTANT_NAME}`, template: `%s · ${INSURER_NAME}` },
  description: `${INSURER_NAME} — individual Health, Motor, Life, Retirement & Savings and Home Takaful plans: buy, claim and renew by talking to ${ASSISTANT_NAME}, our AI assistant.`,
  applicationName: ASSISTANT_NAME,
  appleWebApp: { capable: true, title: ASSISTANT_NAME, statusBarStyle: "black-translucent" },
  icons: { icon: "/brand/logo-mark.png", apple: "/icons/icon-192.png" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0b1830" },
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
  ],
};

// Light by default (like alrajhitakaful.com); respect a stored preference before first paint (no flash).
const themeScript = `try{var t=localStorage.getItem('theme');document.documentElement.classList.toggle('dark',t==='dark')}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Tajawal:wght@400;500;700&display=swap" />
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
