import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { parseEnv } from "node:util";

import type { NextConfig } from "next";

// The repository keeps one .env (from .env.example) at its root, shared with the backend.
// Next.js only reads env files from this folder, so read the root file here and pass its public
// NEXT_PUBLIC_* values through; real environment variables win. Nothing secret reaches the browser.
// (`next` always runs from frontend/; __dirname is unreliable because Next compiles this file.)
const rootEnvFile = path.resolve(process.cwd(), "..", ".env");
const fileEnv = existsSync(rootEnvFile) ? parseEnv(readFileSync(rootEnvFile, "utf8")) : {};
const publicEnv = Object.fromEntries(
  Object.entries({ ...fileEnv, ...process.env }).filter(
    (entry): entry is [string, string] => entry[0].startsWith("NEXT_PUBLIC_") && typeof entry[1] === "string",
  ),
);

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: publicEnv,
  // Lets a second build or server run beside an existing one without sharing .next (e.g. verification).
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
