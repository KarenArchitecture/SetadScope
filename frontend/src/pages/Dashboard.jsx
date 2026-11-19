import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Database,
  FileSearch,
  Gavel,
  LoaderCircle,
  MapPin,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { getAuctionById, getAuctions, getApiHealth } from "../services/api";
import "./Dashboard.css";

const PAGE_SIZE = 20;

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat("fa-IR").format(value);
}

function formatDate(value) {
  if (!value) return "—";
  return value;
}

function StatCard({ icon: Icon, label, value, hint, tone = "blue" }) {
  return (
    <article className="stat-card">
      <div className={`stat-card__icon stat-card__icon--${tone}`}>
        <Icon size={19} />
      </div>
      <div className="stat-card__content">
        <span className="stat-card__label">{label}</span>
        <strong className="stat-card__value">{formatNumber(value)}</strong>
        <span className="stat-card__hint">{hint}</span>
      </div>
    </article>
  );
}

function DetailModal({ auction, loading, onClose }) {
  if (!auction && !loading) return null;

  const fields = auction
    ? [
        ["شناسه ردیف", auction.id],
        ["شناسه مزایده", auction.auction_id],
        ["شماره مزایده", auction.auction_no],
        ["سازمان برگزارکننده", auction.organization],
        ["استان", auction.province],
        ["شهر", auction.city],
        ["مبلغ پایه (مقدار خام)", auction.base_total_price],
        ["مبلغ سپرده (مقدار خام)", auction.trust_amount],
        ["وضعیت", auction.state],
        ["شروع پیشنهادها", auction.proposal_start],
        ["پایان پیشنهادها", auction.proposal_deadline],
      ]
    : [];

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="detail-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="detail-modal__header">
          <div>
            <span className="eyebrow">جزئیات رکورد خام</span>
            <h2 id="detail-title">اطلاعات آگهی</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="بستن">
            <X size={19} />
          </button>
        </header>
        {loading ? (
          <div className="modal-loading"><LoaderCircle className="spin" /> در حال دریافت جزئیات...</div>
        ) : (
          <>
            <h3 className="detail-modal__title">{auction?.title || "بدون عنوان"}</h3>
            <div className="detail-grid">
              {fields.map(([label, value]) => (
                <div className="detail-field" key={label}>
                  <span>{label}</span>
                  <strong>{value === null || value === undefined ? "—" : typeof value === "number" ? formatNumber(value) : value}</strong>
                </div>
              ))}
            </div>
            <p className="detail-modal__note">
              این مقادیر مستقیماً از داده‌های استخراج‌شده نمایش داده می‌شوند؛ واحد پول و معنای تجاری مبالغ هنوز اعتبارسنجی نشده است.
            </p>
          </>
        )}
      </section>
    </div>
  );
}

export default function Dashboard() {
  const [result, setResult] = useState({ items: [], page: 1, pages: 0, total: 0 });
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [apiOnline, setApiOnline] = useState(false);
  const [selectedAuction, setSelectedAuction] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  async function loadPage(nextPage = page, nextSearch = search) {
    setLoading(true);
    setError("");
    try {
      const data = await getAuctions({ search: nextSearch, page: nextPage, pageSize: PAGE_SIZE });
      setResult(data);
      setPage(data.page);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "ارتباط با Backend برقرار نشد. از اجرای FastAPI مطمئن شو.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPage(1, "");
    getApiHealth().then(() => setApiOnline(true)).catch(() => setApiOnline(false));
  }, []);

  const visibleRange = useMemo(() => {
    if (!result.total) return "۰";
    const from = (result.page - 1) * PAGE_SIZE + 1;
    const to = Math.min(result.page * PAGE_SIZE, result.total);
    return `${formatNumber(from)} تا ${formatNumber(to)}`;
  }, [result.page, result.total]);

  const provinceCount = new Set(result.items.map((item) => item.province).filter(Boolean)).size;
  const organizationCount = new Set(result.items.map((item) => item.organization).filter(Boolean)).size;
  const publishedCount = result.items.filter((item) => item.state === "PUBLISHED").length;

  async function handleSearch(event) {
    event.preventDefault();
    const nextSearch = searchInput.trim();
    setSearch(nextSearch);
    await loadPage(1, nextSearch);
  }

  async function openDetails(id) {
    setSelectedAuction(null);
    setDetailLoading(true);
    try {
      const data = await getAuctionById(id);
      setSelectedAuction(data);
    } catch {
      setError("دریافت جزئیات آگهی ناموفق بود.");
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" aria-label="SetadScope">
          <span className="brand__mark"><Activity size={22} /></span>
          <span className="brand__name">Setad<span>Scope</span></span>
        </a>

        <div className="sidebar__section-label">فضای کاری</div>
        <nav className="sidebar-nav">
          <a className="sidebar-nav__item sidebar-nav__item--active" href="#dashboard">
            <Activity size={18} /> نمای کلی
          </a>
          <span className="sidebar-nav__item sidebar-nav__item--muted">
            <Gavel size={18} /> آگهی‌ها <small>به‌زودی</small>
          </span>
          <span className="sidebar-nav__item sidebar-nav__item--muted">
            <Database size={18} /> منابع داده <small>به‌زودی</small>
          </span>
        </nav>

        <div className="sidebar__bottom">
          <div className="pipeline-card">
            <span className="pipeline-card__icon"><FileSearch size={17} /></span>
            <strong>وضعیت پردازش</strong>
            <p>داده‌ها در مرحله جمع‌آوری خام هستند.</p>
            <span className="pipeline-card__status"><span /> بدون تحلیل هوش مصنوعی</span>
          </div>
          <div className="sidebar__version">SETADSCOPE · نسخه ۰.۱</div>
        </div>
      </aside>

      <main className="main-content" id="dashboard">
        <header className="topbar">
          <div className="topbar__breadcrumb">SetadScope <ChevronLeft size={15} /> نمای کلی</div>
          <div className={`connection-status ${apiOnline ? "connection-status--online" : "connection-status--offline"}`}>
            <span /> {apiOnline ? "اتصال به Backend برقرار است" : "در انتظار اتصال به Backend"}
          </div>
        </header>

        <div className="dashboard-content">
          <section className="page-heading">
            <div>
              <span className="eyebrow">مرکز پایش معاملات</span>
              <h1>نمای کلی</h1>
              <p>وضعیت داده‌های جمع‌آوری‌شده از سامانه ستاد</p>
            </div>
            <button className="button button--secondary" onClick={() => loadPage(page, search)} disabled={loading}>
              <RefreshCw size={16} className={loading ? "spin" : ""} /> بروزرسانی
            </button>
          </section>

          <section className="notice-banner">
            <div className="notice-banner__icon"><AlertCircle size={19} /></div>
            <div>
              <strong>داده خام — هنوز تحلیل نشده</strong>
              <p>اطلاعات زیر صرفاً استخراج و یکپارچه‌سازی اولیه شده‌اند. دسته‌بندی تجاری، تشخیص ارتباط با شرکت و پیشنهاد خرید هنوز انجام نشده است.</p>
            </div>
          </section>

          <section className="stats-grid">
            <StatCard icon={Gavel} label="رکوردهای در دسترس API" value={result.total} hint="بر اساس آگهی‌های ذخیره‌شده در PostgreSQL" />
            <StatCard icon={MapPin} label="استان در این صفحه" value={provinceCount} hint="تعداد استان‌های صفحه جاری" tone="violet" />
            <StatCard icon={Building2} label="سازمان در این صفحه" value={organizationCount} hint="تعداد سازمان‌های صفحه جاری" tone="teal" />
            <StatCard icon={CheckCircle2} label="وضعیت منتشرشده در صفحه" value={publishedCount} hint="از ۲۰ رکورد قابل نمایش" tone="amber" />
          </section>

          <section className="data-panel">
            <div className="data-panel__header">
              <div>
                <span className="eyebrow">داده‌های استخراج‌شده</span>
                <h2>فهرست آگهی‌ها</h2>
              </div>
              <span className="raw-tag"><Database size={14} /> داده خام</span>
            </div>

            <form className="search-bar" onSubmit={handleSearch}>
              <Search size={18} />
              <input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="جست‌وجو در عنوان، سازمان یا شهر..."
                aria-label="جست‌وجوی آگهی‌ها"
              />
              {searchInput && <button type="button" className="search-clear" onClick={() => setSearchInput("")} aria-label="پاک کردن"><X size={16} /></button>}
              <button className="button button--primary" type="submit" disabled={loading}>جست‌وجو</button>
            </form>

            {error && (
              <div className="error-state"><AlertCircle size={18} /><span>{error}</span><button onClick={() => loadPage(page, search)}>تلاش مجدد</button></div>
            )}

            <div className="table-wrap">
              <table className="auction-table">
                <thead>
                  <tr>
                    <th>عنوان آگهی</th>
                    <th>سازمان برگزارکننده</th>
                    <th>موقعیت</th>
                    <th>مبلغ پایه خام</th>
                    <th>مهلت پیشنهاد</th>
                    <th>وضعیت</th>
                    <th><span className="sr-only">جزئیات</span></th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan="7" className="table-message"><LoaderCircle className="spin" /> در حال دریافت اطلاعات...</td></tr>
                  ) : result.items.length === 0 ? (
                    <tr><td colSpan="7" className="table-message">رکوردی برای نمایش وجود ندارد.</td></tr>
                  ) : result.items.map((item) => (
                    <tr key={item.id}>
                      <td className="auction-title-cell">
                        <strong>{item.title || "بدون عنوان"}</strong>
                        <span>شناسه: {formatNumber(item.id)}</span>
                      </td>
                      <td>{item.organization || "—"}</td>
                      <td>{[item.city, item.province].filter(Boolean).join("، ") || "—"}</td>
                      <td className="numeric-cell">{formatNumber(item.base_total_price)}</td>
                      <td className="date-cell"><CalendarDays size={14} /> {formatDate(item.proposal_deadline)}</td>
                      <td><span className={`state-pill ${item.state === "PUBLISHED" ? "state-pill--published" : ""}`}>{item.state || "نامشخص"}</span></td>
                      <td><button className="row-action" onClick={() => openDetails(item.id)}>جزئیات <ArrowLeft size={14} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <footer className="table-footer">
              <span>نمایش {visibleRange} از {formatNumber(result.total)} رکورد</span>
              <div className="pagination">
                <button aria-label="صفحه قبل" disabled={loading || page <= 1} onClick={() => loadPage(page - 1, search)}><ChevronRight size={17} /></button>
                <span>صفحه {formatNumber(page)} از {formatNumber(result.pages)}</span>
                <button aria-label="صفحه بعد" disabled={loading || page >= result.pages} onClick={() => loadPage(page + 1, search)}><ChevronLeft size={17} /></button>
              </div>
            </footer>
          </section>

          <footer className="dashboard-footer">
            <span>SetadScope · پایش داده‌های عمومی معاملات</span>
            <span><CircleDollarSign size={14} /> واحد پول مبالغ هنوز تأیید نشده است</span>
          </footer>
        </div>
      </main>

      {(selectedAuction || detailLoading) && (
        <DetailModal auction={selectedAuction} loading={detailLoading} onClose={() => { setSelectedAuction(null); setDetailLoading(false); }} />
      )}
    </div>
  );
}
