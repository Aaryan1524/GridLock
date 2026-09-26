// MapLibre runs its tile/GeoJSON work in an ES-module web worker that imports its shared chunk
// by relative URL. Bundlers cannot rewrite that, so serve both files statically from public/.
// Runs before dev and build; the copies are gitignored so they always match the installed version.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const dist = path.dirname(require.resolve("maplibre-gl/dist/maplibre-gl.css"));
const target = path.resolve(import.meta.dirname, "..", "public", "vendor", "maplibre");
mkdirSync(target, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(path.join(dist, file), path.join(target, file));
}
console.log(`copied MapLibre worker to ${path.relative(process.cwd(), target)}`);
