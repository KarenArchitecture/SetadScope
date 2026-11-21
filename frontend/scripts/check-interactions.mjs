/**
 * Source-level regression checks for critical SetadScope UI interactions.
 * Build and browser testing remain separate; this catches accidental rewiring.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (path) => readFileSync(new URL("../" + path, import.meta.url), "utf8");
const dashboard = read("src/pages/Dashboard.jsx");
const listing = read("src/components/ListingTable.jsx");
const app = read("src/App.jsx");
const transition = read("src/components/ThemeTransition.jsx");
const transitionCss = read("src/components/ThemeTransition.css");
const redesign = read("src/styles/redesign.css");
const settings = read("src/pages/Settings.jsx");

// One keyword-relevance control, on both auction/tender pages,
// integrated into the advanced-search header rather than the category tabs.
assert.equal((dashboard.match(/id="filter-matched-only"/g) || []).length, 1);
assert.match(dashboard, /onMatchedOnlyChange=\{\(checked\) => \{ setMatchedOnly\(checked\); setPage\(1\); \}\}/);
assert.match(dashboard, /activeFilterCount = [^;\n]+Number\(matchedOnly\)/);
const resetStart = dashboard.indexOf("function handleResetFilters()");
const resetEnd = dashboard.indexOf("function handleSort(", resetStart);
assert.ok(resetStart > 0 && resetEnd > resetStart);
assert.match(dashboard.slice(resetStart, resetEnd), /setMatchedOnly\(false\)/);
assert.match(dashboard, /advancedSearch=\{\s*<FiltersPanel/);

// The entire advanced-search panel is passed into the listing after
// the search form and before the data table.
const searchEnd = listing.indexOf("</form>");
const extra = listing.indexOf("{advancedSearch}");
const table = listing.indexOf('<div className="table-wrap">');
assert.ok(searchEnd !== -1 && searchEnd < extra && extra < table);

// Stick the sidebar to the viewport, with its own vertical scroll area.
assert.match(redesign, /position:\s*sticky\s*;/);
assert.match(redesign, /height:\s*100dvh\s*;/);
assert.match(redesign, /overflow-y:\s*auto\s*;/);

// Theme is switched only after the circular cover finishes,
// using synchronous style assignment before the next paint.
assert.match(app, /useLayoutEffect\(\(\) => \{\s*document.documentElement.dataset.theme = theme/);
assert.match(app, /themeTransition.phase === "cover"/);
assert.match(app, /setTheme\(themeTransition.to\)/);
assert.match(app, /phase: "reveal"/);
assert.match(transition, /onAnimationEnd=\{\(event\)/);
assert.match(transitionCss, /clip-path:\s*circle\(0 at var\(--theme-x\)/);
assert.match(transitionCss, /theme-circle-cover/);
assert.match(transitionCss, /theme-circle-reveal/);
assert.match(transitionCss, /theme-transition__progress-fill/);
assert.match(app, /prefers-reduced-motion:\s*reduce/);
assert.match(settings, /onThemeToggle\(event\)/);

console.log("UI interaction checks passed: advanced search, sidebar and theme reveal.");
