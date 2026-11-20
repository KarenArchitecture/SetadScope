import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowDownToLine,
  Building2,
  CheckCircle2,
  CircleDollarSign,
  Database,
  FileSearch,
  FileText,
  Gavel,
  LoaderCircle,
  MapPin,
  Play,
  X,
} from "lucide-react";
import {
  getAuctionById,
  getAuctions,
  getApiHealth,
  getCollectionStatus,
  getTenderById,
  getTenders,
  startCollection,
} from "../services/api";
import ListingTable from "../components/ListingTable";
import "./Dashboard.css";

const PAGE_SIZE = 20;
const ACTIVE_STATES = new Set(["collecting", "importing"]);

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat("fa-IR").format(value);
}

function StatCard({ icon: Icon, label, value, hint, tone = "blue" }) {
  return (
    <article className="stat-card">
      <div className={"stat-card__icon stat-card__icon--" + tone}>
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

function CollectionProgress({ state, kind }) {
  if (!state || state.status === "idle") return null;

  const isTender = kind === "tenders";
  const active = ACTIVE_STATES.has(state.status);
  const percent = Math.max(0, Math.min(100, Number(state.progress_percent || 0)));
  const statusLabel = state.status === "completed"
    ? "با موفقیت تکمیل شد"
    : state.status === "failed"
      ? "اجرای ناموفق"
      : state.status === "importing"
        ? "در حال ذخیره در پایگاه داده"
        : "در حال دریافت از سامانه ستاد";

  return (
    <section className={"collection-progress " + (state.status === "failed" ? "collection-progress--failed" : "")}>
      <div className="collection-progress__top">
        <div>
          <span className="eyebrow">{isTender ? "فرآیند مناقصه‌ها" : "فرآیند مزایده‌ها"}</span>
          <strong>{statusLabel}</strong>
        </div>
        <span className="collection-progress__percent">{formatNumber(percent)}٪</span>
      </div>

      <div
        className="collection-progress__track"
        role="progressbar"
        aria-label="پیشرفت جمع‌آوری اطلاعات"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <div
          className={"collection-progress__fill " + (active ? "collection-progress__fill--active" : "")}
          style={{ width: (active && percent === 0 ? 2 : percent) + "%" }}
        />
      </div>

      <p className="collection-progress__message">{state.message}</p>

      <div className="collection-progress__metrics">
        <span>
          <strong>{formatNumber(state.pages_completed || 0)}</strong>
          {" / "}
          {formatNumber(state.total_pages)}
          {" صفحه"}
        </span>
        <span>
          <strong>{formatNumber(state.records_fetched || 0)}</strong>
          {state.records_total
            ? " / " + formatNumber(state.records_total) + " رکورد دریافت‌شده"
            : " رکورد دریافت‌شده"}
        </span>
        <span>
          <strong>{formatNumber(state.records_stored || 0)}</strong>
          {" رکورد ذخیره‌شده"}
        </span>
      </div>

      {state.status === "failed" && state.error && (
        <details className="collection-progress__error">
          <summary>نمایش جزئیات خطا</summary>
          <pre>{state.error}</pre>
        </details>
      )}

      {state.status === "completed" && state.totals && (
        <div className="collection-progress__summary">
          <CheckCircle2 size={16} />
          {formatNumber(state.totals.fetched)} رکورد بررسی شد؛
          {" "}{formatNumber(state.totals.stored)} رکورد ذخیره شد.
        </div>
      )}
    </section>
  );
}

function DetailModal({ record, kind, loading, onClose }) {
  if (!record && !loading) return null;

  const isTender = kind === "tenders";
  const fields = record
    ? isTender
      ? [
          ["شناسه منبع", record.source_tender_id],
          ["شماره مناقصه", record.tender_number],
          ["نوع فراخوان", record.type_name],
          ["سازمان برگزارکننده", record.organization],
          ["استان", record.province],
          ["شهر", record.city],
          ["تاریخ انتشار", record.public_notification_date],
          ["مهلت دریافت اسناد", record.documents_deadline_date],
          ["مهلت پیشنهاد", record.proposal_deadline_date],
          ["تاریخ بازگشایی", record.opening_date],
          ["وضعیت", record.state],
        ]
      : [
          ["شناسه ردیف", record.id],
          ["شناسه مزایده", record.auction_id],
          ["شماره مزایده", record.auction_no],
          ["سازمان برگزارکننده", record.organization],
          ["استان", record.province],
          ["شهر", record.city],
          ["مبلغ پایه (مقدار خام)", record.base_total_price],
          ["مبلغ سپرده (مقدار خام)", record.trust_amount],
          ["وضعیت", record.state],
          ["شروع پیشنهادها", record.proposal_start],
          ["پایان پیشنهادها", record.proposal_deadline],
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
            <span className="eyebrow">{isTender ? "جزئیات مناقصه" : "جزئیات مزایده"}</span>
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
            <h3 className="detail-modal__title">{record?.title || "بدون عنوان"}</h3>
            <div className="detail-grid">
              {fields.map(([label, value]) => (
                <div className="detail-field" key={label}>
                  <span>{label}</span>
                  <strong>
                    {value === null || value === undefined || value === ""
                      ? "—"
                      : typeof value === "number"
                        ? formatNumber(value)
                        : value}
                  </strong>
                </div>
              ))}
            </div>
            {record?.description && (
              <div className="detail-description">
                <strong>شرح موضوع</strong>
                <p>{record.description}</p>
              </div>
            )}
            {isTender && record?.raw_payload && (
              <details className="raw-json">
                <summary>نمایش پاسخ خام ستاد (JSONB)</summary>
                <pre>{JSON.stringify(record.raw_payload, null, 2)}</pre>
              </details>
            )}
            <p className="detail-modal__note">
              {isTender
                ? "تاریخ‌ها عیناً با قالب دریافتی از ستاد ذخیره شده‌اند؛ تبدیل تقویم یا تفسیر مالی روی آن‌ها انجام نشده است."
                : "مقادیر مالی مستقیماً از داده‌های استخراج‌شده نمایش داده می‌شوند؛ واحد پول و معنای تجاری مبالغ هنوز اعتبارسنجی نشده است."}
            </p>
          </>
        )}
      </section>
    </div>
  );
}

export default function Dashboard({ kind, onNavigate }) {
  const isTender = kind === "tenders";
  const pageTitle = isTender ? "پایش مناقصه‌ها" : "پایش مزایده‌ها";
  const [result, setResult] = useState({ items: [], page: 1, pages: 0, total: 0 });
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [apiOnline, setApiOnline] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [collectionState, setCollectionState] = useState({ status: "idle" });
  const lastRefreshedRun = useRef(null);

  const loadPage = useCallback(async (nextPage = 1, nextSearch = "") => {
    setLoading(true);
    setError("");
    try {
      const fetchPage = isTender ? getTenders : getAuctions;
      const data = await fetchPage({
        search: nextSearch,
        page: nextPage,
        pageSize: PAGE_SIZE,
      });
      setResult(data);
      setPage(data.page);
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          "ارتباط با Backend برقرار نشد. از اجرای سرویس‌ها مطمئن شو.",
      );
    } finally {
      setLoading(false);
    }
  }, [isTender]);

  useEffect(() => {
    loadPage(1, "");
    getApiHealth().then(() => setApiOnline(true)).catch(() => setApiOnline(false));
    getCollectionStatus(kind).then(setCollectionState).catch(() => {});
  }, [kind, loadPage]);

  useEffect(() => {
    if (!ACTIVE_STATES.has(collectionState.status)) return undefined;

    let cancelled = false;
    let requestInFlight = false;
    const timer = window.setInterval(async () => {
      if (requestInFlight) return;
      requestInFlight = true;
      try {
        const nextState = await getCollectionStatus(kind);
        if (cancelled) return;

        setCollectionState(nextState);
        if (
          nextState.status === "completed" &&
          nextState.finished_at &&
          lastRefreshedRun.current !== nextState.finished_at
        ) {
          lastRefreshedRun.current = nextState.finished_at;
          await loadPage(1, search);
        }
      } catch {
        if (!cancelled) setError("دریافت وضعیت لحظه‌ای جمع‌آوری ناموفق بود.");
      } finally {
        requestInFlight = false;
      }
    }, 1000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [collectionState.status, kind, loadPage, search]);

  const provinceCount = new Set(result.items.map((item) => item.province).filter(Boolean)).size;
  const organizationCount = new Set(result.items.map((item) => item.organization).filter(Boolean)).size;
  const fourthStat = isTender
    ? new Set(result.items.map((item) => item.type_name).filter(Boolean)).size
    : result.items.filter((item) => item.state === "PUBLISHED").length;
  const collectionRunning = ACTIVE_STATES.has(collectionState.status);

  const columns = useMemo(() => {
    if (isTender) {
      return [
        {
          key: "title",
          label: "عنوان مناقصه",
          render: (item) => (
            <div className="auction-title-cell">
              <strong>{item.title || "بدون عنوان"}</strong>
              <span>شماره: {item.tender_number || item.source_tender_id}</span>
            </div>
          ),
        },
        { key: "type_name", label: "نوع فراخوان" },
        { key: "organization", label: "سازمان برگزارکننده" },
        {
          key: "location",
          label: "موقعیت",
          render: (item) => [item.city, item.province].filter(Boolean).join("، ") || "—",
        },
        {
          key: "documents_deadline_date",
          label: "مهلت اسناد",
          className: "date-cell",
          render: (item) => item.documents_deadline_date || "—",
        },
        {
          key: "proposal_deadline_date",
          label: "مهلت پیشنهاد",
          className: "date-cell",
          render: (item) => item.proposal_deadline_date || "—",
        },
        {
          key: "opening_date",
          label: "تاریخ بازگشایی",
          className: "date-cell",
          render: (item) => item.opening_date || "—",
        },
      ];
    }

    return [
      {
        key: "title",
        label: "عنوان آگهی",
        render: (item) => (
          <div className="auction-title-cell">
            <strong>{item.title || "بدون عنوان"}</strong>
            <span>شناسه: {formatNumber(item.id)}</span>
          </div>
        ),
      },
      { key: "organization", label: "سازمان برگزارکننده" },
      {
        key: "location",
        label: "موقعیت",
        render: (item) => [item.city, item.province].filter(Boolean).join("، ") || "—",
      },
      {
        key: "base_total_price",
        label: "مبلغ پایه خام",
        className: "numeric-cell",
        render: (item) => formatNumber(item.base_total_price),
      },
      {
        key: "proposal_deadline",
        label: "مهلت پیشنهاد",
        className: "date-cell",
        render: (item) => item.proposal_deadline || "—",
      },
      {
        key: "state",
        label: "وضعیت",
        render: (item) => (
          <span className={"state-pill " + (item.state === "PUBLISHED" ? "state-pill--published" : "")}>
            {item.state || "نامشخص"}
          </span>
        ),
      },
    ];
  }, [isTender]);

  async function handleSearch(event) {
    event.preventDefault();
    const nextSearch = searchInput.trim();
    setSearch(nextSearch);
    await loadPage(1, nextSearch);
  }

  async function handleCollection() {
    setError("");
    try {
      const nextState = await startCollection(kind);
      setCollectionState(nextState);
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          ("شروع جمع‌آوری " + (isTender ? "مناقصه‌ها" : "مزایده‌ها") + " ناموفق بود."),
      );
    }
  }

  async function openDetails(id) {
    setSelectedRecord(null);
    setDetailLoading(true);
    try {
      const data = isTender ? await getTenderById(id) : await getAuctionById(id);
      setSelectedRecord(data);
    } catch {
      setError("دریافت جزئیات آگهی ناموفق بود.");
    } finally {
      setDetailLoading(false);
    }
  }

  const exportHref = search
    ? "/api/" + kind + "/export.xlsx?search=" + encodeURIComponent(search)
    : "/api/" + kind + "/export.xlsx";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="/auctions"
          onClick={(event) => { event.preventDefault(); onNavigate("/auctions"); }}
          aria-label="SetadScope"
        >
          <span className="brand__mark"><Activity size={22} /></span>
          <span className="brand__name">Setad<span>Scope</span></span>
        </a>

        <div className="sidebar__section-label">فضای کاری</div>
        <nav className="sidebar-nav" aria-label="بخش‌های سامانه">
          <a
            href="/auctions"
            className={"sidebar-nav__item " + (!isTender ? "sidebar-nav__item--active" : "")}
            aria-current={!isTender ? "page" : undefined}
            onClick={(event) => { event.preventDefault(); onNavigate("/auctions"); }}
          >
            <Gavel size={18} /> مزایده‌ها
          </a>
          <a
            href="/tenders"
            className={"sidebar-nav__item " + (isTender ? "sidebar-nav__item--active" : "")}
            aria-current={isTender ? "page" : undefined}
            onClick={(event) => { event.preventDefault(); onNavigate("/tenders"); }}
          >
            <FileText size={18} /> مناقصه‌ها
          </a>
          <span className="sidebar-nav__item sidebar-nav__item--muted">
            <Database size={18} /> منابع داده <small>به‌زودی</small>
          </span>
        </nav>

        <div className="sidebar__bottom">
          <div className="pipeline-card">
            <span className="pipeline-card__icon"><FileSearch size={17} /></span>
            <strong>وضعیت پردازش</strong>
            <p>داده‌های هر بخش مستقل جمع‌آوری و در PostgreSQL ذخیره می‌شوند.</p>
            <span className="pipeline-card__status"><span /> بدون تحلیل هوش مصنوعی</span>
          </div>
          <div className="sidebar__version">SETADSCOPE · نسخه ۰.۳</div>
        </div>
      </aside>

      <main className="main-content" id="dashboard">
        <header className="topbar">
          <div className="topbar__breadcrumb">
            SetadScope <span>‹</span> {isTender ? "مناقصه‌ها" : "مزایده‌ها"}
          </div>
          <div className={"connection-status " + (apiOnline ? "connection-status--online" : "connection-status--offline")}>
            <span /> {apiOnline ? "اتصال به Backend برقرار است" : "در انتظار اتصال به Backend"}
          </div>
        </header>

        <div className="dashboard-content">
          <section className="page-heading">
            <div>
              <span className="eyebrow">مرکز پایش معاملات</span>
              <h1>{pageTitle}</h1>
              <p>
                {isTender
                  ? "فراخوان‌های مناقصه از زیرسامانه مستقل مناقصه‌های ستاد"
                  : "آگهی‌های مزایده از زیرسامانه مستقل مزایده‌های ستاد"}
              </p>
            </div>
            <div className="page-heading__actions">
              <button
                className="button button--primary"
                onClick={handleCollection}
                disabled={collectionRunning}
              >
                {collectionRunning ? <LoaderCircle size={16} className="spin" /> : <Play size={16} />}
                {collectionRunning
                  ? "در حال اجرا..."
                  : "جمع‌آوری " + (isTender ? "مناقصه‌ها" : "مزایده‌ها")}
              </button>
              <a className="button button--secondary" href={exportHref}>
                <ArrowDownToLine size={16} /> خروجی Excel
              </a>
            </div>
          </section>

          <CollectionProgress state={collectionState} kind={kind} />

          <section className="notice-banner">
            <div className="notice-banner__icon"><AlertCircle size={19} /></div>
            <div>
              <strong>داده خام — هنوز تحلیل تجاری نشده</strong>
              <p>
                {isTender
                  ? "اطلاعات مناقصه‌ها مستقل از مزایده‌ها دریافت می‌شوند. تاریخ‌های شمسی و پاسخ کامل هر رکورد بدون تبدیل در JSONB نگهداری می‌شوند."
                  : "اطلاعات مزایده‌ها مستقل از مناقصه‌ها دریافت می‌شوند. فیلتر کلیدواژه‌ها در مرحله ورود به پایگاه داده اعمال می‌شود."}
              </p>
            </div>
          </section>

          <section className="stats-grid">
            <StatCard
              icon={isTender ? FileText : Gavel}
              label="کل رکوردهای ذخیره‌شده"
              value={result.total}
              hint={isTender ? "مناقصه‌های موجود در PostgreSQL" : "مزایده‌های موجود در PostgreSQL"}
            />
            <StatCard icon={MapPin} label="استان در این صفحه" value={provinceCount} hint="تعداد استان‌های صفحه جاری" tone="violet" />
            <StatCard icon={Building2} label="سازمان در این صفحه" value={organizationCount} hint="تعداد سازمان‌های صفحه جاری" tone="teal" />
            <StatCard
              icon={CheckCircle2}
              label={isTender ? "نوع فراخوان در این صفحه" : "منتشرشده در این صفحه"}
              value={fourthStat}
              hint={isTender ? "تعداد انواع فراخوان متمایز" : "تعداد رکوردهای با وضعیت PUBLISHED"}
              tone="amber"
            />
          </section>

          <ListingTable
            eyebrow="داده‌های استخراج‌شده"
            title={isTender ? "فهرست مناقصه‌ها" : "فهرست مزایده‌ها"}
            tag="داده خام"
            columns={columns}
            items={result.items}
            loading={loading}
            page={page}
            pages={result.pages}
            total={result.total}
            pageSize={PAGE_SIZE}
            onPageChange={(nextPage) => loadPage(nextPage, search)}
            onDetails={openDetails}
            searchInput={searchInput}
            onSearchInput={setSearchInput}
            onSearch={handleSearch}
            searchPlaceholder={isTender
              ? "جست‌وجو در عنوان، شماره، سازمان یا شرح مناقصه..."
              : "جست‌وجو در عنوان، سازمان یا شهر..."}
            error={error}
            onRetry={() => loadPage(page, search)}
          />

          <footer className="dashboard-footer">
            <span>SetadScope · پایش داده‌های عمومی معاملات</span>
            <span><CircleDollarSign size={14} /> واحد پول مبالغ تا زمان اعتبارسنجی نمایش داده نمی‌شود</span>
          </footer>
        </div>
      </main>

      {(selectedRecord || detailLoading) && (
        <DetailModal
          record={selectedRecord}
          kind={kind}
          loading={detailLoading}
          onClose={() => { setSelectedRecord(null); setDetailLoading(false); }}
        />
      )}
    </div>
  );
}
