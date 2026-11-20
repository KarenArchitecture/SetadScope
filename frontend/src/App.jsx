import { useEffect, useState } from "react";
import Dashboard from "./pages/Dashboard";

function resolvePage() {
  return window.location.pathname.startsWith("/tenders") ? "tenders" : "auctions";
}

export default function App() {
  const [page, setPage] = useState(resolvePage);

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

  return <Dashboard key={page} kind={page} onNavigate={navigate} />;
}
