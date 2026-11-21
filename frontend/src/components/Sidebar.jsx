import { Activity, ChevronsLeft, ChevronsRight, Database, FileSearch, FileText, Gavel, Settings2 } from "lucide-react";

const LINKS = [
  { page: "auctions", path: "/auctions", title: "مزایده‌ها", icon: Gavel },
  { page: "tenders", path: "/tenders", title: "مناقصه‌ها", icon: FileText },
  { page: "settings", path: "/settings", title: "تنظیمات سایت", icon: Settings2 },
];

export default function Sidebar({ page, onNavigate, collapsed, onToggle }) {
  function go(event, path) {
    event.preventDefault();
    onNavigate(path);
  }

  return (
    <aside className={"sidebar " + (collapsed ? "sidebar--collapsed" : "")}>
      <div className="sidebar__top">
        <a className="brand" href="/auctions" onClick={(event) => go(event, "/auctions")} aria-label="SetadScope">
          <span className="brand__mark"><Activity size={22} /></span>
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
      <div className="sidebar__section-label">فضای کاری</div>
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
            <Icon size={19} />
            <span className="sidebar-nav__label">{title}</span>
          </a>
        ))}
        <span className="sidebar-nav__item sidebar-nav__item--muted" aria-label="منابع داده، به‌زودی">
          <Database size={19} /> <span className="sidebar-nav__label">منابع داده <small>به‌زودی</small></span>
        </span>
      </nav>
      <div className="sidebar__bottom">
        <div className="pipeline-card">
          <span className="pipeline-card__icon"><FileSearch size={17} /></span>
          <strong>وضعیت پردازش</strong>
          <p>داده‌های هر بخش مستقل جمع‌آوری و در PostgreSQL ذخیره می‌شوند.</p>
          <span className="pipeline-card__status"><span /> بدون تحلیل هوش مصنوعی</span>
        </div>
        <div className="sidebar__version">SETADSCOPE · نسخه ۰.۴</div>
      </div>
    </aside>
  );
}
