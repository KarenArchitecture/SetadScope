import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { defaultListing, listingTypes } from "./listingTypes";
import QuickActions from "./pages/QuickActions";
import Settings from "./pages/Settings";
import ThemeTransition from "./components/ThemeTransition";
import GlobalSearchPage from "./pages/GlobalSearchPage";
import ToastViewport from "./components/ToastViewport";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import { getApiHealth } from "./services/api";

function resolvePage() {
  if (window.location.pathname.startsWith("/search")) return "search";
  if (window.location.pathname === "/quick") return "quick";
  if (window.location.pathname.startsWith("/settings")) return "settings";
  return listingTypes.find(({ path }) => window.location.pathname.startsWith(path))?.page ?? defaultListing.page;
}

function initialTheme() {
  const saved = window.localStorage.getItem("setadscope-theme");
  if (saved === "light" || saved === "dark") return saved;
  return "dark";
}

function revealGeometry(event) {
  const rect = event?.currentTarget?.getBoundingClientRect?.();
  const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
  const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;
  const radius = Math.ceil(Math.max(
    Math.hypot(x, y),
    Math.hypot(window.innerWidth - x, y),
    Math.hypot(x, window.innerHeight - y),
    Math.hypot(window.innerWidth - x, window.innerHeight - y),
  )) + 12;
  return { x, y, radius };
}

export default function App() {
  const [page, setPage] = useState(resolvePage);
  const [locationSearch, setLocationSearch] = useState(window.location.search);
  const [routeVersion, setRouteVersion] = useState(0);
  const [theme, setTheme] = useState(initialTheme);
  const [themeTransition, setThemeTransition] = useState(null);
  const switchingRef = useRef(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem("setadscope-sidebar-collapsed") === "true");
  const [apiOnline, setApiOnline] = useState(false);

  // Update colors before the browser paints the newly revealed frame.
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("setadscope-theme", theme);
  }, [theme]);

  useEffect(() => {
    window.localStorage.setItem("setadscope-sidebar-collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  // One shared server-health indicator for every page in the application.
  useEffect(() => {
    let active = true;
    let checking = false;

    async function checkServer() {
      if (checking) return;
      checking = true;
      try {
        await getApiHealth();
        if (active) setApiOnline(true);
      } catch {
        if (active) setApiOnline(false);
      } finally {
        checking = false;
      }
    }

    checkServer();
    const interval = window.setInterval(checkServer, 30000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (window.location.pathname === "/") {
      window.history.replaceState({}, "", "/auctions");
    }
    const handlePopState = () => {
      setLocationSearch(window.location.search);
      setPage(resolvePage());
      setRouteVersion((current) => current + 1);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function navigate(path) {
    if (window.location.pathname + window.location.search !== path) window.history.pushState({}, "", path);
    setLocationSearch(window.location.search);
    setPage(resolvePage());
    setRouteVersion((current) => current + 1);
  }

  function updateTableQuery(query) {
    const url = new URL(window.location.href);
    if (query) url.searchParams.set("q", query);
    else url.searchParams.delete("q");
    window.history.replaceState(window.history.state, "", url);
    setLocationSearch(url.search);
  }

  function onThemeToggle(event) {
    if (switchingRef.current) return;
    const to = theme === "dark" ? "light" : "dark";
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setTheme(to);
      return;
    }
    switchingRef.current = true;
    document.documentElement.classList.add("theme-switching");
    setThemeTransition({ ...revealGeometry(event), to, phase: "cover" });
  }

  function onThemeTransitionEnd() {
    if (!themeTransition) return;
    if (themeTransition.phase === "cover") {
      // The page is completely hidden now; switch all tokens in one paint.
      setTheme(themeTransition.to);
      setThemeTransition((current) => current && { ...current, phase: "reveal" });
    } else {
      setThemeTransition(null);
      switchingRef.current = false;
      document.documentElement.classList.remove("theme-switching");
    }
  }

  const onSidebarToggle = () => setSidebarCollapsed((current) => !current);
  const { Page: ListingPage } = listingTypes.find((listing) => listing.page === page) ?? defaultListing;
  const initialQuery = page === "search"
    ? new URLSearchParams(locationSearch).get("q") || ""
    : "";

  return (
    <>
      <div className={"app-shell " + (sidebarCollapsed ? "app-shell--collapsed" : "")}>
        <Sidebar
          page={page}
          onNavigate={navigate}
          collapsed={sidebarCollapsed}
          onToggle={onSidebarToggle}
        />
        <main className="main-content">
          <Topbar
            page={page}
            apiOnline={apiOnline}
            theme={theme}
            onThemeToggle={onThemeToggle}
            onNavigate={navigate}
            initialQuery={initialQuery}
          />
          {page === "quick" ? <QuickActions /> : page === "settings"
            ? <Settings key={routeVersion} theme={theme} onThemeToggle={onThemeToggle} />
            : page === "search"
              ? <GlobalSearchPage key={routeVersion} query={initialQuery} onQueryChange={updateTableQuery} />
              : <ListingPage key={page} kind={page} />}
        </main>
      </div>
      {themeTransition && (
        <ThemeTransition transition={themeTransition} onAnimationEnd={onThemeTransitionEnd} />
      )}
      <ToastViewport />
    </>
  );
}
