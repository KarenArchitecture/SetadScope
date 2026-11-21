import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ChevronDown,
  Building2,
  CalendarDays,
  CheckCircle2,
  CircleDollarSign,
  Database,
  FileSearch,
  FileText,
  Filter,
  Gavel,
  Info,
  LoaderCircle,
  MapPin,
  Play,
  RotateCcw,
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
import Sidebar from "../components/Sidebar";
import ThemeToggle from "../components/ThemeToggle";
import JalaliDatePicker from "../components/JalaliDatePicker";
import "./Dashboard.css";
import "../styles/redesign.css";

const PAGE_SIZE = 20;
const AUCTION_CATEGORIES = [
  { key: "movable", label: "منقول" },
  { key: "immovable", label: "غیرمنقول" },
  { key: "rental", label: "اجاره" },
  { key: "minor", label: "جزئی" },
  { key: "clearance", label: "حراج اموال تملیکی" },
];
const ACTIVE_STATES = new Set(["collecting", "importing"]);
const EMPTY_FILTERS = {
  province: "",
  city: "",
  state: "",
  type_name: "",
  announcement_from: "",
  announcement_to: "",
  deadline_from: "",
  deadline_to: "",
  documents_deadline_from: "",
  documents_deadline_to: "",
  price_min: "",
  price_max: "",
};

function displayState(value) {
  return value === "PUBLISHED" ? "منتشر شده" : (value || "نامشخص");
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat("fa-IR").format(value);
}

function formatDate(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Tehran",
  }).format(parsed);
}

function formatRawDate(value) {
  if (!value) return "—";
  const raw = String(value).trim();
  const jalali = raw.match(/^(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$/);
  if (jalali && Number(jalali[1]) >= 1200 && Number(jalali[1]) <= 1600) {
    const digits = new Intl.NumberFormat("fa-IR", { useGrouping: false });
    const pad = (part) => digits.format(Number(part)).padStart(2, "۰");
    const date = pad(jalali[1]) + "/" + pad(jalali[2]) + "/" + pad(jalali[3]);
    return jalali[4] ? date + "، " + pad(jalali[4]) + ":" + pad(jalali[5]) : date;
  }
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? raw : formatDate(parsed.toISOString());
}

function displayDate(parsedValue, rawValue) {
  return parsedValue ? formatDate(parsedValue) : formatRawDate(rawValue);
}

function remainingTime(value) {
  if (!value) return "نامشخص";
  const difference = new Date(value).getTime() - Date.now();
  if (!Number.isFinite(difference)) return "نامشخص";
  if (difference <= 0) return "مهلت تمام شده";
  const days = Math.floor(difference / 86400000);
  const hours = Math.floor((difference % 86400000) / 3600000);
  if (days > 0) return formatNumber(days) + " روز و " + formatNumber(hours) + " ساعت";
  const minutes = Math.max(1, Math.floor((difference % 3600000) / 60000));
  return formatNumber(hours) + " ساعت و " + formatNumber(minutes) + " دقیقه";
}

function StatCard({ icon: Icon, label, value, hint, archiveValue, tone = "blue" }) {
  return (
    <article className="stat-card">
      <div className={"stat-card__icon stat-card__icon--" + tone}>
        <Icon size={19} />
      </div>
      <div className="stat-card__content">
        <span className="stat-card__label">{label}</span>
        <strong className="stat-card__value">{formatNumber(value)}</strong>
        <span className="stat-card__hint">{hint}</span>
        {archiveValue !== undefined && (
          <span className="stat-card__archive">
            کل آرشیو: {formatNumber(archiveValue)}
          </span>
        )}
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

function FilterField({ label, children, wide = false, className = "" }) {
  return (
    <label className={"filter-field " + (wide ? "filter-field--wide " : "") + className}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function FiltersPanel({
  kind,
  filters,
  options,
  onChange,
  onApply,
  onReset,
  isOpen,
  onToggle,
  activeCount,
  canReset,
}) {
  const isTender = kind === "tenders";
  const provinceOptions = options.provinces || [];
  const cityOptions = (options.cities || [])
    .filter((item) => item.province === filters.province)
    .map((item) => item.city);
  const stateOptions = options.states || [];
  const typeOptions = options.types || [];

  return (
    <section className={"filters-panel " + (isOpen ? "filters-panel--open" : "")}>
      <header className="filters-panel__header">
        <button
          type="button"
          className="filters-panel__toggle"
          onClick={onToggle}
          aria-expanded={isOpen}
        >
          <span className="filters-panel__toggle-main">
            <span className="filters-panel__toggle-icon"><Filter size={16} /></span>
            <span className="filters-panel__toggle-copy">
              <strong>جست‌وجوی پیشرفته</strong>
              <small>
                {activeCount
                  ? toPersianDigits(activeCount) + " فیلتر فعال"
                  : "استان، شهر، وضعیت و بازه‌های زمانی"}
              </small>
            </span>
          </span>
          <span className="filters-panel__toggle-action">
            {isOpen ? "بستن جست‌وجو" : "نمایش جست‌وجو"}
            <ChevronDown className={isOpen ? "filters-panel__chevron filters-panel__chevron--open" : "filters-panel__chevron"} size={17} />
          </span>
        </button>
        <button type="button" className="filters-reset" onClick={onReset} disabled={!canReset} title="حذف تمام فیلترهای انتخابی و اعمال‌شده">
          <RotateCcw size={14} /> حذف فیلترها
        </button>
      </header>

      <div className="filters-panel__collapsible" aria-hidden={!isOpen} inert={!isOpen}>
        <div className="filters-panel__collapsible-content">
          <div className="filters-panel__body">
            <div className={"filters-grid " + (isTender ? "filters-grid--tenders" : "filters-grid--auctions")}>
              <FilterField label="استان">
                <select value={filters.province} onChange={(event) => onChange("province", event.target.value)}>
                  <option value="">همه استان‌ها</option>
                  {provinceOptions.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </FilterField>

              <FilterField label="شهر">
                <select
                  value={filters.city}
                  disabled={!filters.province}
                  onChange={(event) => onChange("city", event.target.value)}
                >
                  <option value="">{filters.province ? "همه شهرهای استان" : "ابتدا استان را انتخاب کنید"}</option>
                  {cityOptions.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </FilterField>

              <FilterField label="وضعیت آگهی">
                <select value={filters.state} onChange={(event) => onChange("state", event.target.value)}>
                  <option value="">همه وضعیت‌ها</option>
                  {stateOptions.map((value) => <option key={value} value={value}>{displayState(value)}</option>)}
                </select>
              </FilterField>

              {isTender ? (
                <FilterField label="نوع فراخوان">
                  <select value={filters.type_name} onChange={(event) => onChange("type_name", event.target.value)}>
                    <option value="">همه انواع</option>
                    {typeOptions.map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                </FilterField>
              ) : (
                <>
                  <FilterField label="حداقل مبلغ پایه" className="filter-field--price">
                    <input
                      type="number"
                      min="0"
                      step="any"
                      inputMode="decimal"
                      placeholder="از مبلغ"
                      value={filters.price_min}
                      onChange={(event) => onChange("price_min", event.target.value)}
                    />
                  </FilterField>
                  <FilterField label="حداکثر مبلغ پایه" className="filter-field--price">
                    <input
                      type="number"
                      min="0"
                      step="any"
                      inputMode="decimal"
                      placeholder="تا مبلغ"
                      value={filters.price_max}
                      onChange={(event) => onChange("price_max", event.target.value)}
                    />
                  </FilterField>
                </>
              )}

              <div className="filter-date-group">
                <div className="filter-date-group__title">
                  <CalendarDays size={14} />
                  {isTender ? "بازه تاریخ اعلام مناقصه" : "بازه تاریخ اعلام / نمایش مزایده"}
                </div>
                <div className="filter-date-group__inputs">
                  <FilterField label="از تاریخ">
                    <JalaliDatePicker
                      value={filters.announcement_from}
                      onChange={(value) => onChange("announcement_from", value)}
                      ariaLabel="از تاریخ اعلام به شمسی"
                    />
                  </FilterField>
                  <FilterField label="تا تاریخ">
                    <JalaliDatePicker
                      value={filters.announcement_to}
                      onChange={(value) => onChange("announcement_to", value)}
                      ariaLabel="تا تاریخ اعلام به شمسی"
                    />
                  </FilterField>
                </div>
              </div>

              <div className="filter-date-group">
                <div className="filter-date-group__title">
                  <CalendarDays size={14} />
                  بازه مهلت پیشنهاد
                </div>
                <div className="filter-date-group__inputs">
                  <FilterField label="از تاریخ">
                    <JalaliDatePicker
                      value={filters.deadline_from}
                      onChange={(value) => onChange("deadline_from", value)}
                      ariaLabel="از تاریخ مهلت پیشنهاد به شمسی"
                    />
                  </FilterField>
                  <FilterField label="تا تاریخ">
                    <JalaliDatePicker
                      value={filters.deadline_to}
                      onChange={(value) => onChange("deadline_to", value)}
                      ariaLabel="تا تاریخ مهلت پیشنهاد به شمسی"
                    />
                  </FilterField>
                </div>
              </div>

              {isTender && (
                <div className="filter-date-group">
                  <div className="filter-date-group__title">
                    <CalendarDays size={14} />
                    بازه مهلت دریافت اسناد
                  </div>
                  <div className="filter-date-group__inputs">
                    <FilterField label="از تاریخ">
                      <JalaliDatePicker
                        value={filters.documents_deadline_from}
                        onChange={(value) => onChange("documents_deadline_from", value)}
                        ariaLabel="از تاریخ مهلت اسناد به شمسی"
                      />
                    </FilterField>
                    <FilterField label="تا تاریخ">
                      <JalaliDatePicker
                        value={filters.documents_deadline_to}
                        onChange={(value) => onChange("documents_deadline_to", value)}
                        ariaLabel="تا تاریخ مهلت اسناد به شمسی"
                      />
                    </FilterField>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="filters-panel__footer">
            <span>فیلترها روی کل آرشیو اعمال می‌شوند، نه فقط رکوردهای صفحه جاری.</span>
            <button type="button" className="button button--primary" onClick={onApply}>
              <Filter size={15} /> اعمال فیلترها
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function toPersianDigits(value) {
  return new Intl.NumberFormat("fa-IR").format(value);
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
          ["تاریخ انتشار", displayDate(record.public_notification_at, record.public_notification_date)],
          ["مهلت دریافت اسناد", displayDate(record.documents_deadline_at, record.documents_deadline_date)],
          ["مهلت پیشنهاد", displayDate(record.proposal_deadline_at, record.proposal_deadline_date)],
          ["تاریخ بازگشایی", displayDate(record.opening_at, record.opening_date)],
          ["وضعیت", displayState(record.state)],
        ]
      : [
          ["شناسه ردیف", record.id],
          ["دسته مزایده", AUCTION_CATEGORIES.find((item) => item.key === record.category)?.label],
          ["شناسه منبع", record.source_party_id],
          ["شناسه مزایده", record.auction_id],
          ["عنوان مورد", record.item_title],
          ["شماره مورد", record.item_reference_no],
          ["نوع مال", record.asset_type],
          ["نوع مبلغ", record.price_type],
          ["مدت اجاره (ماه)", record.rent_duration_months],
          ["شماره مزایده", record.auction_no],
          ["سازمان برگزارکننده", record.organization],
          ["استان", record.province],
          ["شهر", record.city],
          ["مبلغ پایه", record.base_total_price],
          ["مبلغ سپرده", record.trust_amount],
          ["تاریخ اعلام / شروع نمایش", displayDate(record.announcement_at, null)],
          ["پایان نمایش آگهی", displayDate(record.site_show_end_at, null)],
          ["شروع انتشار", displayDate(record.publish_start_at, null)],
          ["پایان انتشار", displayDate(record.publish_finish_at, null)],
          ["تاریخ ایجاد در سامانه", displayDate(record.source_created_at, null)],
          ["آخرین ویرایش", displayDate(record.last_modify_at, null)],
          ["شروع پیشنهادها", displayDate(record.proposal_start, null)],
          ["پایان پیشنهادها", displayDate(record.proposal_deadline, null)],
          ["اعلام برنده", displayDate(record.winner_announce_at, null)],
          ["تاریخ باز شدن", displayDate(record.opened_at, null)],
          ["تاریخ بازگشایی", displayDate(record.opening_at, null)],
          ["افتتاح سپرده", displayDate(record.trust_opened_at, null)],
          ["وضعیت", displayState(record.state)],
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
            {record?.raw_payload && (
              <details className="raw-json">
                <summary>نمایش پاسخ خام ستاد (JSONB)</summary>
                <pre>{JSON.stringify(record.raw_payload, null, 2)}</pre>
              </details>
            )}
            <p className="detail-modal__note">
              {isTender
                ? "تاریخ شمسی اصلی حفظ شده و مقدار متناظر میلادی برای مرتب‌سازی و فیلتر در پایگاه داده نگهداری می‌شود."
                : "تاریخ‌های شمسی منبع به زمان استاندارد قابل مقایسه تبدیل شده‌اند؛ پاسخ خام منبع نیز حفظ شده است. واحد پول مبالغ هنوز از منبع تأیید نشده است."}
            </p>
          </>
        )}
      </section>
    </div>
  );
}

export default function Dashboard({ kind, onNavigate, theme, onThemeToggle, sidebarCollapsed, onSidebarToggle }) {
  const isTender = kind === "tenders";
  const pageTitle = isTender ? "پایش مناقصه‌ها" : "پایش مزایده‌ها";
  const [auctionCategory, setAuctionCategory] = useState("movable");
  const [matchedOnly, setMatchedOnly] = useState(!isTender);
  const selectedCategoryLabel = AUCTION_CATEGORIES.find((item) => item.key === auctionCategory)?.label || "منقول";
  const [result, setResult] = useState({
    items: [],
    page: 1,
    pages: 0,
    total: 0,
    archive_stats: {},
    filter_options: {},
  });
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [filterDraft, setFilterDraft] = useState({ ...EMPTY_FILTERS });
  const [appliedFilters, setAppliedFilters] = useState({ ...EMPTY_FILTERS });
  const [filtersOpen, setFiltersOpen] = useState(false);
  const activeFilterCount = Object.values(appliedFilters).filter((value) => value !== "").length;
  const canResetFilters = activeFilterCount > 0 || Object.values(filterDraft).some((value) => value !== "");
  const [sortBy, setSortBy] = useState(isTender ? "announcement_at" : "proposal_deadline");
  const [sortDir, setSortDir] = useState(isTender ? "desc" : "asc");
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [apiOnline, setApiOnline] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [collectionState, setCollectionState] = useState({ status: "idle" });
  const lastRefreshedRun = useRef(null);
  const lastRequestId = useRef(0);

  const loadPage = useCallback(async (nextPage = 1) => {
    const requestId = ++lastRequestId.current;
    setLoading(true);
    setError("");
    try {
      const fetchPage = isTender ? getTenders : getAuctions;
      const data = await fetchPage({
        search,
        ...appliedFilters,
        matched_only: matchedOnly,
        ...(!isTender ? { category: auctionCategory } : {}),
        sortBy,
        sortDir,
        page: nextPage,
        pageSize,
      });
      if (requestId !== lastRequestId.current) return;
      setResult(data);
      setPage(data.page);
    } catch (requestError) {
      if (requestId !== lastRequestId.current) return;
      setError(
        requestError.response?.data?.detail ||
          "ارتباط با Backend برقرار نشد. از اجرای سرویس‌ها مطمئن شو.",
      );
    } finally {
      if (requestId === lastRequestId.current) setLoading(false);
    }
  }, [isTender, auctionCategory, matchedOnly, search, appliedFilters, sortBy, sortDir, pageSize]);

  useEffect(() => {
    loadPage(1);
  }, [loadPage]);

  useEffect(() => {
    let active = true;
    getApiHealth().then(() => { if (active) setApiOnline(true); }).catch(() => { if (active) setApiOnline(false); });
    getCollectionStatus(kind, auctionCategory).then((status) => {
      if (active) setCollectionState(status);
    }).catch(() => {});
    return () => { active = false; };
  }, [kind, auctionCategory]);

  useEffect(() => {
    if (!ACTIVE_STATES.has(collectionState.status)) return undefined;
    let cancelled = false;
    let requestInFlight = false;
    const timer = window.setInterval(async () => {
      if (requestInFlight) return;
      requestInFlight = true;
      try {
        const nextState = await getCollectionStatus(kind, auctionCategory);
        if (cancelled) return;
        setCollectionState(nextState);
        if (
          nextState.status === "completed" &&
          nextState.finished_at &&
          lastRefreshedRun.current !== nextState.finished_at
        ) {
          lastRefreshedRun.current = nextState.finished_at;
          await loadPage(1);
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
  }, [collectionState.status, kind, auctionCategory, loadPage]);

  const provinceCount = new Set(result.items.map((item) => item.province).filter(Boolean)).size;
  const organizationCount = new Set(result.items.map((item) => item.organization).filter(Boolean)).size;
  const fourthStat = isTender
    ? new Set(result.items.map((item) => item.type_name).filter(Boolean)).size
    : auctionCategory === "clearance"
      ? result.items.filter((item) => item.has_keyword_match).length
      : result.items.filter((item) => item.state === "PUBLISHED").length;
  const archiveStats = result.archive_stats || {};
  const collectionRunning = ACTIVE_STATES.has(collectionState.status);

  const columns = useMemo(() => {
    if (isTender) {
      return [
        {
          key: "title",
          label: "عنوان مناقصه",
          sortable: true,
          sortKey: "title",
          render: (item) => (
            <div className="auction-title-cell">
              <strong>{item.title || "بدون عنوان"}</strong>
              <span>شماره: {item.tender_number || item.source_tender_id}</span>
            </div>
          ),
        },
        { key: "type_name", label: "نوع فراخوان", sortable: true, sortKey: "type_name" },
        { key: "organization", label: "سازمان برگزارکننده", sortable: true, sortKey: "organization" },
        { key: "city", label: "شهر", sortable: true, sortKey: "city" },
        { key: "province", label: "استان", sortable: true, sortKey: "province" },
        {
          key: "announcement_at",
          label: "تاریخ اعلام",
          sortable: true,
          sortKey: "announcement_at",
          className: "date-cell",
          render: (item) => formatDate(item.public_notification_at),
        },
        {
          key: "documents_deadline_at",
          label: "مهلت اسناد",
          sortable: true,
          sortKey: "documents_deadline_at",
          className: "date-cell",
          render: (item) => formatDate(item.documents_deadline_at),
        },
        {
          key: "proposal_deadline_at",
          label: "زمان باقی‌مانده",
          sortable: true,
          sortKey: "proposal_deadline_at",
          render: (item) => (
            <div className="deadline-cell">
              <strong>{remainingTime(item.proposal_deadline_at)}</strong>
              <span>{formatDate(item.proposal_deadline_at)}</span>
            </div>
          ),
        },
      ];
    }

    return [
      {
        key: "title",
        label: "عنوان آگهی",
        sortable: true,
        sortKey: "title",
        render: (item) => (
          <div className="auction-title-cell">
            <strong>{item.title || "بدون عنوان"}</strong>
            <span>شناسه: {formatNumber(item.id)}</span>
          </div>
        ),
      },
      ...(auctionCategory === "rental" ? [{
        key: "item_title",
        label: "مورد اجاره",
        sortable: true,
        sortKey: "item_title",
        render: (item) => (
          <div className="auction-title-cell">
            <strong>{item.item_title || "—"}</strong>
            <span>مدت: {item.rent_duration_months ?? "—"} ماه</span>
          </div>
        ),
      }] : []),
      ...(auctionCategory === "immovable" ? [{
        key: "item_title",
        label: "ملک / نوع ملک",
        sortable: true,
        sortKey: "item_title",
        render: (item) => item.asset_type || item.item_title || "—",
      }] : []),
      ...(auctionCategory === "clearance" ? [{
        key: "asset_type",
        label: "دسته‌بندی کالا",
        sortable: true,
        sortKey: "asset_type",
        render: (item) => item.asset_type || "—",
      }] : []),
      { key: "organization", label: "سازمان برگزارکننده", sortable: true, sortKey: "organization" },
      { key: "city", label: "شهر", sortable: true, sortKey: "city" },
      { key: "province", label: "استان", sortable: true, sortKey: "province" },
      {
        key: "base_total_price",
        label: auctionCategory === "rental" ? "مبلغ پایه اجاره" : auctionCategory === "clearance" ? "مبلغ پایه (ریال)" : "مبلغ پایه",
        sortable: true,
        sortKey: "base_total_price",
        className: "numeric-cell",
        render: (item) => formatNumber(item.base_total_price),
      },
      {
        key: "announcement_at",
        label: "تاریخ اعلام",
        sortable: true,
        sortKey: "announcement_at",
        className: "date-cell",
        render: (item) => formatDate(item.announcement_at),
      },
      {
        key: "proposal_deadline",
        label: "زمان باقی‌مانده",
        sortable: true,
        sortKey: "proposal_deadline",
        render: (item) => (
          <div className="deadline-cell">
            <strong>{remainingTime(item.proposal_deadline)}</strong>
            <span>{formatDate(item.proposal_deadline)}</span>
          </div>
        ),
      },
      {
        key: "state",
        label: auctionCategory === "clearance" ? "کد وضعیت" : "وضعیت",
        sortable: true,
        sortKey: "state",
        render: (item) => (
          <span className={"state-pill " + (item.state === "PUBLISHED" ? "state-pill--published" : "")}>
            {displayState(item.state)}
          </span>
        ),
      },
    ];
  }, [isTender, auctionCategory]);

  function handleCategoryChange(category) {
    if (category === auctionCategory) return;
    lastRequestId.current += 1;
    setAuctionCategory(category);
    setSearch("");
    setSearchInput("");
    setFilterDraft({ ...EMPTY_FILTERS });
    setAppliedFilters({ ...EMPTY_FILTERS });
    setPage(1);
    setSortBy("proposal_deadline");
    setSortDir("asc");
    setFiltersOpen(false);
    setResult({ items: [], page: 1, pages: 0, total: 0, archive_stats: {}, filter_options: {} });
    setCollectionState({ status: "idle" });
    lastRefreshedRun.current = null;
  }

  function handleSearch(event) {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  }

  function handleFilterChange(name, value) {
    setFilterDraft((current) => ({
      ...current,
      [name]: value,
      ...(name === "province" ? { city: "" } : {}),
    }));
  }

  function handleApplyFilters() {
    const min = filterDraft.price_min === "" ? null : Number(filterDraft.price_min);
    const max = filterDraft.price_max === "" ? null : Number(filterDraft.price_max);
    if (!isTender && min !== null && max !== null && min > max) {
      setError("حداقل مبلغ نمی‌تواند از حداکثر مبلغ بیشتر باشد.");
      return;
    }
    const dateRanges = [
      ["announcement_from", "announcement_to"],
      ["deadline_from", "deadline_to"],
      ["documents_deadline_from", "documents_deadline_to"],
    ];
    const hasInvalidDateRange = dateRanges.some(([fromKey, toKey]) =>
      filterDraft[fromKey] && filterDraft[toKey] && filterDraft[fromKey] > filterDraft[toKey]
    );
    if (hasInvalidDateRange) {
      setError("تاریخ شروع هر بازه نمی‌تواند بعد از تاریخ پایان آن باشد.");
      return;
    }
    setError("");
    setPage(1);
    setAppliedFilters({ ...filterDraft });
    setFiltersOpen(false);
  }

  function handleResetFilters() {
    setFilterDraft({ ...EMPTY_FILTERS });
    setAppliedFilters({ ...EMPTY_FILTERS });
    setError("");
    setPage(1);
  }

  function handleSort(key) {
    if (sortBy === key) {
      setSortDir((current) => current === "asc" ? "desc" : "asc");
    } else {
      setSortBy(key);
      setSortDir(key === "base_total_price" || key === "announcement_at" && isTender ? "desc" : "asc");
    }
    setPage(1);
  }

  async function handleCollection() {
    setError("");
    try {
      const nextState = await startCollection(kind, auctionCategory);
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

  const exportParams = new URLSearchParams();
  const exportValues = {
    search,
    ...appliedFilters,
    matched_only: matchedOnly,
    ...(!isTender ? { category: auctionCategory } : {}),
    sort_by: sortBy,
    sort_dir: sortDir,
  };
  Object.entries(exportValues).forEach(([key, value]) => {
    if (value !== "" && value !== undefined && value !== null) exportParams.set(key, String(value));
  });
  const exportHref = "/api/" + kind + "/export.xlsx?" + exportParams.toString();

  return (
    <div className={"app-shell " + (sidebarCollapsed ? "app-shell--collapsed" : "")}>
      <Sidebar page={kind} onNavigate={onNavigate} collapsed={sidebarCollapsed} onToggle={onSidebarToggle} />

      <main className="main-content" id="dashboard">
        <header className="topbar">
          <div className="topbar__breadcrumb">
            SetadScope <span>‹</span> {isTender ? "مناقصه‌ها" : "مزایده‌ها"}
          </div>
          <div className="topbar__actions">
            <div className={"connection-status " + (apiOnline ? "connection-status--online" : "connection-status--offline")}>
              <span /> {apiOnline ? "اتصال به Backend برقرار است" : "در انتظار اتصال به Backend"}
            </div>
            <ThemeToggle theme={theme} onToggle={onThemeToggle} />
          </div>
        </header>

        <div className="dashboard-content">
          <section className="page-heading">
            <div>
              <span className="eyebrow">مرکز پایش معاملات</span>
              <div className="page-heading__title-row">
                <h1>{pageTitle}</h1>
                <span
                  className="page-heading__info"
                  title="تاریخ‌ها در صفحه به تقویم شمسی نمایش داده می‌شوند. مرتب‌سازی و فیلتر بر اساس زمان استاندارد ذخیره‌شده در پایگاه داده انجام می‌شود."
                  aria-label="راهنمای تاریخ‌ها"
                  tabIndex={0}
                >
                  <Info size={16} />
                </span>
              </div>
              <p>
                {isTender
                  ? "فراخوان‌های مناقصه از زیرسامانه مستقل مناقصه‌های ستاد"
                  : "آگهی‌های " + selectedCategoryLabel + " از زیرسامانه مزایده‌های ستاد"}
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
                  : "جمع‌آوری " + (isTender ? "مناقصه‌ها" : selectedCategoryLabel)}
              </button>
              <a className="button button--secondary" href={exportHref}>
                <ArrowDownToLine size={16} /> خروجی Excel
              </a>
            </div>
          </section>

          <section className="auction-category-nav" aria-label="فیلتر ارتباط با کلیدواژه‌ها">
              {!isTender && <div className="auction-category-nav__tabs" role="tablist" aria-label="نوع مزایده">
                {AUCTION_CATEGORIES.map(({ key, label }) => (
                  <button
                    key={key}
                    role="tab"
                    type="button"
                    className={"auction-category-nav__tab " + (auctionCategory === key ? "auction-category-nav__tab--active" : "")}
                    aria-selected={auctionCategory === key}
                    onClick={() => handleCategoryChange(key)}
                  >
                    {label}
                  </button>
                ))}
              </div>}
              <label className="auction-category-nav__match">
                <input
                  type="checkbox"
                  checked={matchedOnly}
                  onChange={(event) => { setMatchedOnly(event.target.checked); setPage(1); }}
                />
                فقط آگهی‌های مرتبط با کلیدواژه‌ها
              </label>
          </section>
          {!isTender && auctionCategory === "clearance" && (
            <div className="auction-category-note">
              حراج: فعلاً فقط آگهی‌های سازمان جمع‌آوری و فروش اموال تملیکی (شناسه ۵۳۱۵)
            </div>
          )}
          <CollectionProgress state={collectionState} kind={kind} />

          <section className="stats-grid">
            <StatCard
              icon={isTender ? FileText : Gavel}
              label="رکورد در نتایج"
              value={result.total}
              hint={matchedOnly ? "فقط آگهی‌های مرتبط" : isTender ? "رکوردهای منطبق با فیلتر فعلی" : "همه آگهی‌های دسته انتخاب‌شده"}
              archiveValue={archiveStats.total}
            />
            <StatCard
              icon={MapPin}
              label="استان در این صفحه"
              value={provinceCount}
              hint="تعداد استان‌های متمایز در صفحه جاری"
              archiveValue={archiveStats.province_count}
              tone="violet"
            />
            <StatCard
              icon={Building2}
              label="سازمان در این صفحه"
              value={organizationCount}
              hint="تعداد سازمان‌های متمایز در صفحه جاری"
              archiveValue={archiveStats.organization_count}
              tone="teal"
            />
            <StatCard
              icon={CheckCircle2}
              label={isTender ? "نوع فراخوان در این صفحه" : auctionCategory === "clearance" ? "مرتبط در این صفحه" : "منتشرشده در این صفحه"}
              value={fourthStat}
              hint={isTender ? "تعداد انواع فراخوان متمایز" : auctionCategory === "clearance" ? "طبق کلیدواژه‌ها" : "تعداد آگهی‌های منتشرشده"}
              archiveValue={isTender ? archiveStats.type_count : auctionCategory === "clearance" ? archiveStats.matched_total : archiveStats.published_count}
              tone="amber"
            />
          </section>

          <FiltersPanel
            kind={kind}
            filters={filterDraft}
            options={result.filter_options || {}}
            onChange={handleFilterChange}
            onApply={handleApplyFilters}
            onReset={handleResetFilters}
            isOpen={filtersOpen}
            onToggle={() => setFiltersOpen((current) => !current)}
            activeCount={activeFilterCount}
            canReset={canResetFilters}
          />

          <ListingTable
            eyebrow="داده‌های استخراج‌شده"
            title={isTender ? "فهرست مناقصه‌ها" : "فهرست مزایده‌های " + selectedCategoryLabel}
            tag="داده قابل فیلتر"
            columns={columns}
            items={result.items}
            loading={loading}
            page={page}
            pages={result.pages}
            total={result.total}
            pageSize={pageSize}
            onPageChange={(nextPage) => loadPage(nextPage)}
            onPageSizeChange={(nextSize) => { setPage(1); setPageSize(nextSize); }}
            onDetails={openDetails}
            searchInput={searchInput}
            onSearchInput={setSearchInput}
            onSearch={handleSearch}
            searchPlaceholder={isTender
              ? "جست‌وجو در عنوان، شماره، سازمان یا شرح مناقصه..."
              : "جست‌وجو در عنوان، سازمان، شهر یا شماره مزایده..."}
            error={error}
            onRetry={() => loadPage(page)}
            sortBy={sortBy}
            sortDir={sortDir}
            onSort={handleSort}
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
