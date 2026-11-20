import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  Building2,
  CalendarDays,
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
const COLLECTION_ACTIVE_STATES = new Set(["collecting", "importing"]);

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

function DetailModal({ record, type, loading, onClose }) {
  if (!record && !loading) return null;

  const isTender = type === "tenders";
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

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState("auctions");
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

  async function loadPage(nextPage = page, nextSearch = search, nextType = activeTab) {
    setLoading(true);
    setError("");
    try {
      const fetchPage = nextType === "tenders" ? getTenders : getAuctions;
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
  }

  useEffect(() => {
    loadPage(1, search, activeTab);
  }, [activeTab]);

  useEffect(() => {
    getApiHealth().then(() => setApiOnline(true)).catch(() => setApiOnline(false));
    getCollectionStatus().then(setCollectionState).catch(() => {});
  }, []);

  useEffect(() => {
    if (!COLLECTION_ACTIVE_STATES.has(collectionState.status)) return undefined;

    let cancelled = false;
    let timer;
    const pollStatus = async () => {
      try {
        const status = await getCollectionStatus();
        if (cancelled) return;
        setCollectionState(status);

        if (status.status === "completed") {
          if (activeTab === "auctions") await loadPage(1, search, "auctions");
          if (timer) window.clearInterval(timer);
        } else if (status.status === "failed" && timer) {
          window.clearInterval(timer);
        }
      } catch {
        if (!cancelled) setError("دریافت وضعیت اجرای Collector ناموفق بود.");
      }
    };

    timer = window.setInterval(pollStatus, 1800);
    pollStatus();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [collectionState.status, activeTab, search]);

  const visibleRange = useMemo(() => {
    if (!result.total) return "۰";
    const from = (result.page - 1) * PAGE_SIZE + 1;
    const to = Math.min(result.page * PAGE_SIZE, result.total);
    return formatNumber(from) + " تا " + formatNumber(to);
  }, [result.page, result.total]);

  const provinceCount = new Set(result.items.map((item) => item.province).filter(Boolean)).size;
  const organizationCount = new Set(result.items.map((item) => item.organization).filter(Boolean)).size;
  const fourthStat = activeTab === "auctions"
    ? result.items.filter((item) => item.state === "PUBLISHED").length
    : new Set(result.items.map((item) => item.type_name).filter(Boolean)).size;
  const collectionRunning = COLLECTION_ACTIVE_STATES.has(collectionState.status);

  const columns = useMemo(() => {
    if (activeTab === "tenders") {
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
  }, [activeTab]);

  async function handleSearch(event) {
    event.preventDefault();
    const nextSearch = searchInput.trim();
    setSearch(nextSearch);
    await loadPage(1, nextSearch, activeTab);
  }

  async function handleCollection() {
    setError("");
    try {
      const status = await startCollection();
      setCollectionState(status);
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
          "شروع جمع‌آوری مزایده‌ها ناموفق بود. وضعیت Backend را بررسی کن.",
      );
    }
  }

  async function openDetails(id) {
    setSelectedRecord(null);
    setDetailLoading(true);
    try {
      const data = activeTab === "tenders"
        ? await getTenderById(id)
        : await getAuctionById(id);
      setSelectedRecord(data);
    } catch {
      setError("دریافت جزئیات آگهی ناموفق بود.");
    } finally {
      setDetailLoading(false);
    }
  }

  let collectionMessage = "";
  if (collectionState.status === "collecting") {
    collectionMessage = "در حال دریافت صفحات مزایده‌ها...";
  } else if (collectionState.status === "importing") {
    collectionMessage = "دریافت تمام شد؛ در حال فیلتر و ذخیره اطلاعات...";
  } else if (collectionState.status === "completed" && collectionState.totals) {
    const totals = collectionState.totals;
    collectionMessage = "موفق: " + formatNumber(totals.fetched) + " دریافت، " +
      formatNumber(totals.stored) + " ذخیره";
  } else if (collectionState.status === "failed") {
    collectionMessage = collectionState.error || "اجرای جمع‌آوری ناموفق بود.";
  }

  const isTender = activeTab === "tenders";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#dashboard" aria-label="SetadScope">
          <span className="brand__mark"><Activity size={22} /></span>
          <span className="brand__name">Setad<span>Scope</span></span>
        </a>

        <div className="sidebar__section-label">فضای کاری</div>
        <nav className="sidebar-nav">
          <button
            className={"sidebar-nav__item " + (!isTender ? "sidebar-nav__item--active" : "")}
            onClick={() => setActiveTab("auctions")}
          >
            <Gavel size={18} /> مزایده‌ها
          </button>
          <button
            className={"sidebar-nav__item " + (isTender ? "sidebar-nav__item--active" : "")}
            onClick={() => setActiveTab("tenders")}
          >
            <FileText size={18} /> مناقصه‌ها
          </button>
          <span className="sidebar-nav__item sidebar-nav__item--muted">
            <Database size={18} /> منابع داده <small>به‌زودی</small>
          </span>
        </nav>

        <div className="sidebar__bottom">
          <div className="pipeline-card">
            <span className="pipeline-card__icon"><FileSearch size={17} /></span>
            <strong>وضعیت پردازش</strong>
            <p>داده‌ها در مرحله جمع‌آوری و یکپارچه‌سازی اولیه هستند.</p>
            <span className="pipeline-card__status"><span /> بدون تحلیل هوش مصنوعی</span>
          </div>
          <div className="sidebar__version">SETADSCOPE · نسخه ۰.۲</div>
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
              <h1>{isTender ? "پایش مناقصه‌ها" : "پایش مزایده‌ها"}</h1>
              <p>اطلاعات استخراج‌شده از سامانه تدارکات الکترونیکی دولت</p>
            </div>
            {!isTender && (
              <div className="page-heading__actions">
                <button
                  className="button button--primary"
                  onClick={handleCollection}
                  disabled={collectionRunning}
                >
                  {collectionRunning ? <LoaderCircle size={16} className="spin" /> : <Play size={16} />}
                  {collectionRunning ? "در حال اجرا..." : "جمع‌آوری مزایده‌ها"}
                </button>
                {collectionMessage && (
                  <span
                    className={"collection-feedback " + (collectionState.status === "failed" ? "collection-feedback--error" : "")}
                    title={collectionState.status === "failed" ? collectionMessage : undefined}
                  >
                    {collectionMessage}
                  </span>
                )}
              </div>
            )}
          </section>

          <section className="notice-banner">
            <div className="notice-banner__icon"><AlertCircle size={19} /></div>
            <div>
              <strong>داده خام — هنوز تحلیل تجاری نشده</strong>
              <p>
                {isTender
                  ? "رکوردهای مناقصه با شناسه منبع یکتا ذخیره می‌شوند. تاریخ‌های شمسی و پاسخ کامل هر رکورد بدون تبدیل در JSONB نگهداری می‌شوند."
                  : "اطلاعات مزایده‌ها استخراج و یکپارچه‌سازی اولیه شده‌اند. دسته‌بندی تجاری و پیشنهاد فرصت‌های مرتبط هنوز انجام نشده است."}
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

          <div className="listing-tabs" role="tablist" aria-label="نوع آگهی">
            <button
              role="tab"
              aria-selected={!isTender}
              className={!isTender ? "listing-tabs__button listing-tabs__button--active" : "listing-tabs__button"}
              onClick={() => setActiveTab("auctions")}
            >
              <Gavel size={16} /> مزایده‌ها
            </button>
            <button
              role="tab"
              aria-selected={isTender}
              className={isTender ? "listing-tabs__button listing-tabs__button--active" : "listing-tabs__button"}
              onClick={() => setActiveTab("tenders")}
            >
              <FileText size={16} /> مناقصه‌ها
            </button>
          </div>

          <ListingTable
            eyebrow="داده‌های استخراج‌شده"
            title={isTender ? "فهرست مناقصه‌ها" : "فهرست مزایده‌ها"}
            tag={<><Database size={14} /> داده خام</>}
            columns={columns}
            items={result.items}
            loading={loading}
            page={page}
            pages={result.pages}
            total={result.total}
            pageSize={PAGE_SIZE}
            onPageChange={(nextPage) => loadPage(nextPage, search, activeTab)}
            onDetails={openDetails}
            searchInput={searchInput}
            onSearchInput={setSearchInput}
            onSearch={handleSearch}
            searchPlaceholder={isTender
              ? "جست‌وجو در عنوان، شماره، سازمان یا شرح مناقصه..."
              : "جست‌وجو در عنوان، سازمان یا شهر..."}
            error={error}
            onRetry={() => loadPage(page, search, activeTab)}
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
          type={activeTab}
          loading={detailLoading}
          onClose={() => { setSelectedRecord(null); setDetailLoading(false); }}
        />
      )}
    </div>
  );
}
