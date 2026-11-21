import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Dashboard from "./pages/Dashboard";
import Settings from "./pages/Settings";
import ThemeTransition from "./components/ThemeTransition";
import GlobalSearchPage from "./pages/GlobalSearchPage";

function resolvePage() {
  if (window.location.pathname.startsWith("/search")) return "search";
  if (window.location.pathname.startsWith("/settings")) return "settings";
  return window.location.pathname.startsWith("/tenders") ? "tenders" : "auctions";
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
  const [routeVersion, setRouteVersion] = useState(0);
  const [theme, setTheme] = useState(initialTheme);
  const [themeTransition, setThemeTransition] = useState(null);
  const switchingRef = useRef(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem("setadscope-sidebar-collapsed") === "true");

  // Update colors before the browser paints the newly revealed frame.
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("setadscope-theme", theme);
  }, [theme]);

  useEffect(() => {
    window.localStorage.setItem("setadscope-sidebar-collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => {
    if (window.location.pathname === "/") {
      window.history.replaceState({}, "", "/auctions");
    }
    const handlePopState = () => {
      setPage(resolvePage());
      setRouteVersion((current) => current + 1);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function navigate(path) {
    if (window.location.pathname !== path) window.history.pushState({}, "", path);
    setPage(resolvePage());
    setRouteVersion((current) => current + 1);
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
  return (
    <>
      {page === "settings"
        ? <Settings onNavigate={navigate} theme={theme} onThemeToggle={onThemeToggle} sidebarCollapsed={sidebarCollapsed} onSidebarToggle={onSidebarToggle} />
        : page === "search"
          ? <GlobalSearchPage key={routeVersion} onNavigate={navigate} theme={theme} onThemeToggle={onThemeToggle} sidebarCollapsed={sidebarCollapsed} onSidebarToggle={onSidebarToggle} />
          : <Dashboard key={page} kind={page} onNavigate={navigate} theme={theme} onThemeToggle={onThemeToggle} sidebarCollapsed={sidebarCollapsed} onSidebarToggle={onSidebarToggle} />}
      {themeTransition && (
        <ThemeTransition transition={themeTransition} onAnimationEnd={onThemeTransitionEnd} />
      )}
    </>
  );
}
