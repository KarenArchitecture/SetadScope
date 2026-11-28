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
const globalCollection = read("src/components/GlobalCollectionControl.jsx");
const sidebar = read("src/components/Sidebar.jsx");

// All three listings reuse the same quick filters and clear both on reset.
const filters = read("src/components/FiltersPanel.jsx");
const filterState = read("src/hooks/useListingFilters.js");
assert.match(filters, /checked=\{matchedOnly\}/);
assert.match(filters, /checked=\{todayOnly\}/);
assert.match(filters, /فقط آگهی‌های مرتبط/);
assert.match(filters, /فقط آگهی‌های امروز/);
assert.match(filterState, /setMatchedOnly\(false\)/);
assert.match(filterState, /setTodayOnly\(false\)/);
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
assert.ok(topbar.includes('<GlobalCollectionControl apiOnline={apiOnline} />'));
assert.match(globalCollection, /role="dialog"/);
assert.match(globalCollection, /getGlobalCollectionStatus/);
assert.match(globalCollection, /startGlobalCollection/);
assert.match(globalCollection, /failed_sources/);
assert.match(globalCollection, /منبع/);
assert.match(topbar, /اتصال به سرور برقرار است/);

// The global refresh control stays beside search in a dedicated, stable header zone.
// At narrower widths, search and refresh share their own row below breadcrumb/actions.
const topbarLayoutStart = redesign.indexOf("/* Four stable header zones:");
const topbarResponsiveStart = redesign.indexOf("/* Keep the search and global refresh adjacent", topbarLayoutStart);
assert.ok(topbarLayoutStart >= 0 && topbarResponsiveStart > topbarLayoutStart);
const desktopTopbarLayout = redesign.slice(topbarLayoutStart, topbarResponsiveStart);
const responsiveTopbarLayout = redesign.slice(topbarResponsiveStart, redesign.indexOf("/* Unified, fixed-footprint collection/export action card.", topbarResponsiveStart));
assert.match(desktopTopbarLayout, /display:\s*grid/);
assert.match(desktopTopbarLayout, /grid-template-columns:\s*minmax\(0, 1fr\) minmax\(0, 470px\) auto minmax\(0, 1fr\)/);
assert.match(desktopTopbarLayout, /grid-template-areas:\s*"breadcrumb search global-collection actions"/);
assert.match(desktopTopbarLayout, /\.topbar > \.global-search-bar\s*\{[^}]*grid-area:\s*search/s);
assert.match(desktopTopbarLayout, /\.global-collection-control\s*\{[^}]*grid-area:\s*global-collection/s);
assert.match(responsiveTopbarLayout, /grid-template-areas:\s*"breadcrumb actions"\s*"search global-collection"/);
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
assert.ok(api.includes('api.post("/api/collection/global/run")'));
assert.ok(api.includes('api.get("/api/collection/global/status")'));
assert.match(searchApi, /@router\.get\("\/api\/search"\)/);
assert.match(searchApi, /union_all\(\*projections\)/);
assert.match(globalSearchPage, /kind === "all"/);
assert.match(globalSearchPage, /listingTypes\.map/);
assert.match(globalSearchPage, /listing\.getDetails/);
assert.match(listing, /key=\{item\.row_key \|\| item\.id\}/);
assert.match(listing, /onDetails\(item\.id, item\)/);
assert.match(globalSearchPage, /onSearch=\{submitSearch\}/);
assert.match(globalSearchPage, /advancedSearch=\{\s*<FiltersPanel/);

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
const retryWait = read("src/components/CollectionWait.jsx");
assert.match(app, /<ToastViewport \/>/);
assert.match(dashboard, /className="collection-action-card"/);
assert.match(dashboard, /collection-action-card__last-updated/);
assert.match(dashboard, /notifyToast\(\s*"loading"/);
assert.match(dashboard, /notifyToast\(\s*nextState\.status === "completed" \? "success" : "error"/);
assert.match(dashboard, /notifyToast\(\s*"error"/);
assert.match(toastViewport, /setadscope:toast/);
assert.match(toastViewport, /aria-live="polite"/);
assert.match(toastViewport, /TOAST_ICONS/);
assert.match(toastStyles, /app-toast-enter/);
assert.match(toastUtils, /export function notifyToast/);
assert.match(dashboard, /import CollectionWait from/);
assert.match(dashboard, /<CollectionWait state={state} \/>/);
assert.match(globalCollection, /<CollectionWait state={state} \/>/);
assert.match(retryWait, /retryClearance\(retryId, collectionGroup\)/);
assert.match(retryWait, /retryId && now < deadline/);
assert.match(dashboard, /state\.resumable/);
assert.match(dashboard, /onRetry=\{handleCollection\}/);
assert.match(dashboard, /resume_page/);
assert.match(dashboard, /تلاش مجدد از صفحه/);

console.log("Toast and resumable clearance retry interaction checks passed.");
