import { useEffect, useState } from "react";
import Dashboard from "./pages/Dashboard";
import Settings from "./pages/Settings";

function resolvePage() {
  if (window.location.pathname.startsWith("/settings")) return "settings";
  return window.location.pathname.startsWith("/tenders") ? "tenders" : "auctions";
}

function initialTheme() {
  const saved = window.localStorage.getItem("setadscope-theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [page, setPage] = useState(resolvePage);
  const [theme, setTheme] = useState(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("setadscope-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (window.location.pathname === "/") {
      window.history.replaceState({}, "", "/auctions");
    }
    const handlePopState = () => setPage(resolvePage());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function navigate(path) {
    if (window.location.pathname !== path) window.history.pushState({}, "", path);
    setPage(resolvePage());
  }

  const onThemeToggle = () => setTheme((current) => current === "dark" ? "light" : "dark");
  return page === "settings"
    ? <Settings onNavigate={navigate} theme={theme} onThemeToggle={onThemeToggle} />
    : <Dashboard key={page} kind={page} onNavigate={navigate} theme={theme} onThemeToggle={onThemeToggle} />;
}
