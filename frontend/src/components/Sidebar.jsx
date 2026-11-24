import { Activity, ChevronsLeft, ChevronsRight, Database, Search, Settings2 } from "lucide-react";

import { listingTypes } from "../listingTypes";

const LINKS = [
  { page: "search", path: "/search", title: "همه آگهی‌ها", icon: Search },
  ...listingTypes,
  { page: "settings", path: "/settings", title: "تنظیمات سایت", icon: Settings2 },
];

export default function Sidebar({ page, onNavigate, collapsed, onToggle }) {
  function go(event, path) {
    event.preventDefault();
    onNavigate(path);
  }

  return (
    <aside
      className={"sidebar " + (collapsed ? "sidebar--collapsed" : "")}
      aria-label="ناوبری اصلی SetadScope"
    >
      <div className="sidebar__top">
        <a className="brand" href="/auctions" onClick={(event) => go(event, "/auctions")} aria-label="SetadScope">
          <span className="brand__mark"><Activity size={21} strokeWidth={2.1} /></span>
          <span className="brand__name">Setad<span>Scope</span></span>
        </a>
        <button
          className="sidebar__collapse"
          type="button"
          aria-label={collapsed ? "باز کردن سایدبار" : "جمع کردن سایدبار"}
          aria-expanded={!collapsed}
          title={collapsed ? "باز کردن سایدبار" : "جمع کردن سایدبار"}
          onClick={onToggle}
        >
          {collapsed ? <ChevronsLeft size={18} /> : <ChevronsRight size={18} />}
        </button>
      </div>

      <div className="sidebar__section-label">
        <span>فضای کاری</span>
      </div>

      <nav className="sidebar-nav" aria-label="بخش‌های سامانه">
        {LINKS.map(({ page: id, path, title, icon: Icon }) => (
          <a
            key={id}
            href={path}
            title={collapsed ? title : undefined}
            className={"sidebar-nav__item " + (page === id ? "sidebar-nav__item--active" : "")}
            aria-current={page === id ? "page" : undefined}
            aria-label={title}
            onClick={(event) => go(event, path)}
          >
            <span className="sidebar-nav__icon"><Icon size={19} strokeWidth={1.9} /></span>
            <span className="sidebar-nav__label">{title}</span>
          </a>
        ))}
        <span
          className="sidebar-nav__item sidebar-nav__item--muted"
          aria-label="منابع داده، به‌زودی"
          title={collapsed ? "منابع داده، به‌زودی" : undefined}
        >
          <span className="sidebar-nav__icon"><Database size={19} strokeWidth={1.9} /></span>
          <span className="sidebar-nav__label">
            منابع داده
            <small className="sidebar-nav__soon">به‌زودی</small>
          </span>
        </span>
      </nav>

      <div className="sidebar__bottom">
        <div className="sidebar__version">SETADSCOPE <span>·</span> نسخه ۰.۴</div>
      </div>
    </aside>
  );
}
