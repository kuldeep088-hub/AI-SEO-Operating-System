import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import "./globals.css";

/* DESIGN.md names Inter Variable and Berkeley Mono. Berkeley Mono is a paid
   licence, so this uses the substitute the doc itself lists (JetBrains Mono).
   next/font downloads both at build time and serves them from our own origin —
   no runtime request to Google, which keeps /privacy's "no third-party calls"
   claim true as well as being faster. */
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
  // The system's weight band. DESIGN.md caps it at 590 and says the
  // absence of bold is deliberate, so 700+ is not loaded at all.
  weight: ["300", "400", "500", "600"],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono-jetbrains",
  display: "swap",
  weight: ["400"],
});

export const metadata: Metadata = {
  title: "AI SEO Operating System",
  description:
    "Search Console and Analytics for every client site, in one place, refreshed nightly.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable}`}
      // The system has no light mode — darkness is the substrate, not a
      // theme. Declaring it stops the browser painting white on first frame.
      style={{ colorScheme: "dark" }}
    >
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
