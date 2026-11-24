import GlobalSearchBar from "./GlobalSearchBar";
import GlobalCollectionControl from "./GlobalCollectionControl";
import ThemeToggle from "./ThemeToggle";

import { listingTypes } from "../listingTypes";

const PAGE_TITLES = {
  ...Object.fromEntries(listingTypes.map(({ page, title }) => [page, title])),
  search: "همه آگهی‌ها",
  settings: "تنظیمات سایت",
};

export default function Topbar({
  page,
  apiOnline,
  theme,
  onThemeToggle,
  onNavigate,
  initialQuery = "",
}) {
  return (
    <header className="topbar">
      <div className="topbar__breadcrumb">
        SetadScope <span>‹</span> {PAGE_TITLES[page] || PAGE_TITLES.auctions}
      </div>
      <GlobalSearchBar onNavigate={onNavigate} initialQuery={initialQuery} />
      <GlobalCollectionControl apiOnline={apiOnline} />
      <div className="topbar__actions">
        <div
          className={"connection-status " + (apiOnline ? "connection-status--online" : "connection-status--offline")}
          role="status"
          aria-live="polite"
          title={apiOnline ? "ارتباط با سرویس سرور برقرار است" : "ارتباط با سرویس سرور برقرار نیست"}
        >
          <span aria-hidden="true" />
          {apiOnline ? "اتصال به سرور برقرار است" : "اتصال به سرور برقرار نیست"}
        </div>
        <ThemeToggle theme={theme} onToggle={onThemeToggle} />
      </div>
    </header>
  );
}
