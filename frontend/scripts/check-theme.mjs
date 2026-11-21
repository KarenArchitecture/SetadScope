/**
 * Guard against reintroducing the former navy/sky-blue palette.
 * Runs with Node only; no browser or test framework required.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const load = (relative) => readFileSync(new URL("../" + relative, import.meta.url), "utf8");
const global = load("src/styles/global.css");
const legacy = load("src/pages/Dashboard.css");
const design = load("src/styles/redesign.css");
const settings = load("src/pages/Settings.css");

const dark = global.match(/html\[data-theme="dark"\]\s*\{([^}]+)\}/)?.[1];
assert.ok(dark, "The global dark-theme tokens must exist.");
assert.match(dark, /--page-bg:\s*#171717\s*;/i);
assert.match(dark, /--surface:\s*#202020\s*;/i);
assert.match(dark, /--accent:\s*#d5b783\s*;/i);
assert.doesNotMatch(design, /--page-bg:\s*#[a-f0-9]{6}\s*;/i,
  "Theme colors should only be defined in global.css.");
assert.doesNotMatch(legacy, /Theme overrides of legacy hard-coded presentation colors/,
  "Legacy dark-mode overrides must not return.");

assert.match(design, /\.topbar\s*\{[^}]*background:\s*var\(--surface\)/s);
assert.match(design, /\.auction-table thead\s*\{[^}]*background:\s*var\(--surface-soft\)/s);
assert.match(design, /\.sidebar\s*\{[^}]*background:\s*var\(--sidebar-bg\)/s);

// Consider only chromatic cyan/blue/violet declarations, ignoring grayscale.
function isBlueTint(hex) {
  const raw = hex.slice(1, 7);
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(raw.slice(i, i + 2), 16) / 255);
  const max = Math.max(r, g, b);
  const delta = max - Math.min(r, g, b);
  if (delta === 0) return false;
  const hue = ((max === r ? (g - b) / delta % 6
    : max === g ? (b - r) / delta + 2
      : (r - g) / delta + 4) * 60 + 360) % 360;
  return hue >= 180 && hue <= 280 && delta / max > 0.013;
}

for (const [name, css] of Object.entries({
  "global.css": global,
  "Dashboard.css": legacy,
  "redesign.css": design,
  "Settings.css": settings,
})) {
  // Comments are ignored so descriptive documentation doesn't trip the guard.
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const blues = [...withoutComments.matchAll(/#[\da-f]{6}(?:[\da-f]{2})?\b/gi)]
    .map(([hex]) => hex)
    .filter(isBlueTint);
  assert.deepEqual(blues, [], name + " contains a legacy blue-tinted color.");
}

console.log("Theme palette checks passed: charcoal surfaces and bronze accents.");
