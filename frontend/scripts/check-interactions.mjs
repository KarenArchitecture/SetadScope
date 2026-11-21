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
const topbar = read("src/components/Topbar.jsx");
const sidebar = read("src/components/Sidebar.jsx");

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

// Keep the sidebar anchored, while only its navigation region can scroll.
// The scrollbar is visually hidden so it does not compete with the navigation.
assert.match(redesign, /position:\s*sticky\s*;/);
assert.match(redesign, /height:\s*100dvh\s*;/);
assert.match(redesign, /\.sidebar-nav\s*\{[^}]*overflow-y:\s*auto/s);
assert.match(redesign, /\.sidebar-nav::-webkit-scrollbar\s*\{\s*display:\s*none;/);
assert.match(redesign, /\.sidebar,\s*\.app-shell--collapsed \.sidebar\s*\{[^}]*overflow:\s*hidden;/s);
assert.match(sidebar, /className="sidebar-nav__icon"/);
assert.match(sidebar, /className="sidebar-nav__soon"/);

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


// Global search is available from the topbar and sidebar on every workspace page.
const globalSearchPage = read("src/pages/GlobalSearchPage.jsx");
const globalSearchBar = read("src/components/GlobalSearchBar.jsx");
const api = read("src/services/api.js");
const searchApi = read("../backend/app/search_api.py");
assert.match(app, /pathname\.startsWith\("\/search"\)/);
assert.match(app, /<GlobalSearchPage key=\{routeVersion\}/);
assert.match(app, /<Topbar/);
assert.match(topbar, /<GlobalSearchBar onNavigate=\{onNavigate\} initialQuery=\{initialQuery\}/);
assert.match(topbar, /اتصال به سرور برقرار است/);
assert.doesNotMatch(dashboard, /<header className="topbar"/);
assert.doesNotMatch(settings, /<header className="topbar"/);
assert.doesNotMatch(globalSearchPage, /<header className="topbar"/);
assert.doesNotMatch(dashboard, /<GlobalSearchBar/);
assert.doesNotMatch(settings, /<GlobalSearchBar/);
assert.doesNotMatch(globalSearchPage, /<GlobalSearchBar/);
assert.match(app, /<Sidebar/);
assert.match(sidebar, /page: "search", path: "\/search"/);
assert.doesNotMatch(sidebar, /وضعیت پردازش/);
assert.match(globalSearchBar, /Ctrl K/);
assert.match(globalSearchBar, /onNavigate\(query \? "\/search\?q="/);
assert.match(globalSearchBar, /event\.key\.toLowerCase\(\) === "k"/);
assert.match(api, /api\.get\("\/api\/search"/);
assert.match(searchApi, /@router\.get\("\/api\/search"\)/);
assert.match(searchApi, /union_all\(auction_query, tender_query\)/);
assert.match(globalSearchPage, /kind === "all"/);
assert.match(globalSearchPage, /kind === "auction"/);
assert.match(globalSearchPage, /kind === "tender"/);
assert.match(globalSearchPage, /getAuctionById/);
assert.match(globalSearchPage, /getTenderById/);
assert.match(listing, /key=\{item\.row_key \|\| item\.id\}/);
assert.match(listing, /onDetails\(item\.id, item\)/);
assert.match(globalSearchPage, /hideSearch/);

console.log("Global search checks passed: all transaction types, navigation and details.");


// Collection history is persisted and the latest successful run is scoped
// to the selected auction category or the tender dataset.
const dashboardCss = read("src/pages/Dashboard.css");
const mainApi = read("../backend/app/main.py");
const models = read("../backend/app/db/models.py");
const auctionIngestion = read("../backend/app/services/auction_ingestion.py");
const tenderIngestion = read("../backend/app/services/tender_ingestion.py");
const migration = read("../backend/alembic/versions/0008_ingestion_run_scope.py");
assert.match(dashboard, /function formatLastCollectionUpdate\(value\)/);
assert.match(dashboard, /timeZone = "Asia\/Tehran"/);
assert.match(dashboard, /dayKey\(updatedAt\) === dayKey\(new Date\(\)\)/);
assert.match(dashboard, /collectionState\.last_updated_at/);
assert.match(dashboard, /className="collection-action-card__last-updated"/);
assert.match(redesign, /\.collection-action-card__last-updated/);
assert.match(mainApi, /def latest_successful_collection_at\(/);
assert.match(mainApi, /IngestionRun\.status == "success"/);
assert.match(mainApi, /state\["last_updated_at"\]/);
assert.match(models, /class IngestionRun\(Base\)/);
assert.match(models, /kind: Mapped\[str \| None\]/);
assert.match(models, /category: Mapped\[str \| None\]/);
assert.match(auctionIngestion, /IngestionRun\(status="running", kind="auctions", category=category\)/);
assert.match(tenderIngestion, /IngestionRun\(status="running", kind="tenders", category=None\)/);
assert.match(tenderIngestion, /run\.finished_at = datetime\.now\(timezone\.utc\)/);
assert.match(migration, /revision = "0008"/);
assert.match(migration, /ix_ingestion_runs_scope_finished/);

console.log("Collection timestamp checks passed: persistent history and Tehran-local display.");


// Stable collection actions and accessible toast lifecycle notifications.
const toastViewport = read("src/components/ToastViewport.jsx");
const toastStyles = read("src/components/ToastViewport.css");
const toastUtils = read("src/utils/toast.js");
assert.match(app, /<ToastViewport \/>/);
assert.match(dashboard, /className="collection-action-card"/);
assert.match(dashboard, /collection-action-card__last-updated/);
assert.match(dashboard, /notifyToast\(\s*"loading"/);
assert.match(dashboard, /notifyToast\(\s*"success"/);
assert.match(dashboard, /notifyToast\(\s*"error"/);
assert.match(toastViewport, /setadscope:toast/);
assert.match(toastViewport, /aria-live="polite"/);
assert.match(toastViewport, /TOAST_ICONS/);
assert.match(toastStyles, /app-toast-enter/);
assert.match(toastUtils, /export function notifyToast/);

console.log("Toast checks passed: request, success, error and accessible viewport.");
