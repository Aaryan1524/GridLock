import "@fontsource/instrument-serif/400.css";
import "@fontsource/instrument-serif/400-italic.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DEFAULT_THEME, THEME_INIT_SCRIPT } from "@/lib/themeScript";

export const metadata: Metadata = {
  title: "GridLock — cross-utility transmission coordination",
  description:
    "GridLock compares public transmission plans from neighboring utilities, verifies where projects sit, and surfaces the coordination opportunities worth acting on.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    // The init script may change data-theme before hydration, hence suppressHydrationWarning on <html> only.
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} data-theme={DEFAULT_THEME} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
