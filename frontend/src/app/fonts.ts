import localFont from "next/font/local";

// The display serif, self-hosted from @fontsource (no network at build or run time). Loading it
// through next/font preloads the file and gives the fallback matching metrics, so headlines don't
// jump when the font arrives. Latin covers every character the interface uses.
export const instrumentSerif = localFont({
  src: [
    { path: "../../node_modules/@fontsource/instrument-serif/files/instrument-serif-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "../../node_modules/@fontsource/instrument-serif/files/instrument-serif-latin-400-italic.woff2", weight: "400", style: "italic" },
  ],
  variable: "--font-instrument-serif",
  display: "swap",
  adjustFontFallback: "Times New Roman",
});
