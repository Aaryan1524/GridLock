// Runtime settings from the repository .env (see .env.example). Each variable is referenced
// literally so Next.js can inline it into the browser bundle.

function number(value: string | undefined): number | null {
  const parsed = Number(value);
  return value && Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export const runtimeConfig = {
  apiBaseUrl: (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/+$/, ""),
  apiService: process.env.NEXT_PUBLIC_API_SERVICE ?? "",
  mapStyleUrl: process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "",
  mapStyleUrlLight: process.env.NEXT_PUBLIC_MAP_STYLE_URL_LIGHT ?? "",
  mapStyleTimeoutMs: number(process.env.NEXT_PUBLIC_MAP_STYLE_TIMEOUT_MS),
} as const;

export function missingConfig(): string[] {
  const missing: string[] = [];
  if (!runtimeConfig.apiBaseUrl) missing.push("NEXT_PUBLIC_API_BASE_URL");
  if (!runtimeConfig.apiService) missing.push("NEXT_PUBLIC_API_SERVICE");
  return missing;
}
