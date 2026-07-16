// Rasterize build/icon.majaz.svg -> build/icon.majaz.png (512) + icon.majaz.ico.
//
// Needs two dev deps that are NOT installed by default (kept out of the app):
//   npm i -D sharp png-to-ico
// Then: node scripts/gen-icons.mjs
//
// FONT NOTE: the icon glyph is Arabic (مَ). The rasterizer (sharp/librsvg) draws
// text with fonts installed on the machine — install Vazirmatn (or rely on the
// Tahoma/Segoe UI fallback) or the glyph may render as a tofu box. If you have a
// design tool, exporting the .png/.ico by hand from icon.majaz.svg is just as
// valid; this script is only a convenience.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const buildDir = join(here, "..", "build");
const svg = readFileSync(join(buildDir, "icon.majaz.svg"));

let sharp, pngToIco;
try {
  sharp = (await import("sharp")).default;
  pngToIco = (await import("png-to-ico")).default;
} catch (e) {
  console.error(
    "[gen-icons] missing deps. Run: npm i -D sharp png-to-ico\n" +
      `(import failed: ${e.message})`,
  );
  process.exit(1);
}

// Main PNG (Linux AppImage icon + ico source).
const png512 = await sharp(svg).resize(512, 512).png().toBuffer();
writeFileSync(join(buildDir, "icon.majaz.png"), png512);

// Windows .ico bundles several sizes.
const sizes = [16, 24, 32, 48, 64, 128, 256];
const pngs = await Promise.all(
  sizes.map((s) => sharp(svg).resize(s, s).png().toBuffer()),
);
writeFileSync(join(buildDir, "icon.majaz.ico"), await pngToIco(pngs));

console.log("[gen-icons] wrote build/icon.majaz.png + build/icon.majaz.ico");
