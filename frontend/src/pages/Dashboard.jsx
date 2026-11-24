import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Building2,
  CheckCircle2,
  CircleDollarSign,
  Check,
  FileText,
  Gavel,
  Info,
  LoaderCircle,
  MapPin,
  Play,
  SlidersHorizontal,
  X,
} from "lucide-react";
import {
  getAuctionById,
  getAuctions,
  getCollectionStatus,
  getTenderById,
  getTenders,
  listingQueryParams,
  startCollection,
} from "../services/api";
import ListingTable from "../components/ListingTable";
import ExcelExportButton from "../components/ExcelExportButton";
import FiltersPanel from "../components/FiltersPanel";
import useListingFilters from "../hooks/useListingFilters";
import { notifyToast } from "../utils/toast";
import "./Dashboard.css";
import "../styles/redesign.css";

const PAGE_SIZE = 20;
const AUCTION_GROUPS = [
  { key: "all", label: "همه" },
  { key: "executive_agencies", label: "دستگاه‌های اجرایی" },
  { key: "amval_tamliki", label: "سازمان جمع‌آوری و فروش اموال تملیکی" },
];
const AUCTION_CATEGORIES = [
  { key: "movable", label: "منقول" },
  { key: "immovable", label: "غیرمنقول" },
  { key: "rental", label: "اجاره" },
  { key: "minor", label: "جزئی" },
  { key: "clearance", label: "حراج مشترک" },
];
const CATEGORY_LABELS = Object.fromEntries(AUCTION_CATEGORIES.map(({ key, label }) => [key, label]));
const GROUP_LABELS = {
  ...Object.fromEntries(AUCTION_GROUPS.map(({ key, label }) => [key, label])),
  shared: "حراج مشترک",
};
const ACTIVE_STATES = new Set(["collecting", "importing", "running"]);
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

function formatLastCollectionUpdate(value) {
  if (!value) return "آخرین بروزرسانی: ثبت نشده";
  const updatedAt = new Date(value);
  if (Number.isNaN(updatedAt.getTime())) return "آخرین بروزرسانی: ثبت نشده";

  const timeZone = "Asia/Tehran";
  const time = new Intl.DateTimeFormat("fa-IR", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone,
  }).format(updatedAt);
  const dayKey = (date) => {
    const parts = new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      timeZone,
    }).formatToParts(date);
    const values = Object.fromEntries(
      parts.filter((part) => ["year", "month", "day"].includes(part.type))
        .map((part) => [part.type, part.value]),
    );
    return values.year + "-" + values.month + "-" + values.day;
  };

  if (dayKey(updatedAt) === dayKey(new Date())) {
    return "آخرین بروزرسانی: " + time;
  }

  const date = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone,
  }).format(updatedAt);
  return "آخرین بروزرسانی: " + date + "، " + time;
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

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  archiveValue,
  pageLabel = "در صفحه جاری",
  tone = "blue",
}) {
  const archiveCount = archiveValue === undefined ? value : archiveValue;

  return (
    <article className="stat-card">
      <div className={"stat-card__icon stat-card__icon--" + tone}>
        <Icon size={19} />
      </div>
      <div className="stat-card__content">
        <span className="stat-card__label">{label}</span>
        <strong className="stat-card__value">{formatNumber(archiveCount)}</strong>
        <span className="stat-card__page-count">
          {pageLabel}: {formatNumber(value)}
        </span>
        <span className="stat-card__hint">{hint}</span>
      </div>
    </article>
  );
}

function CollectionProgress({ state, kind, onDismiss }) {
  if (!state || state.status === "idle") return null;

  const isBatch = state.kind === "auction_batch";
  const active = ACTIVE_STATES.has(state.status);
  const finished = state.status === "completed" || state.status === "completed_with_errors";
  const percent = Math.max(0, Math.min(100, Number(
    (isBatch ? state.overall_progress_percent : state.progress_percent) || 0,
  )));
  const statusLabel = {
    completed: "با موفقیت تکمیل شد",
    completed_with_errors: "جمع‌آوری با خطا پایان یافت",
    failed: "اجرای ناموفق",
    importing: "در حال ذخیره در پایگاه داده",
    running: "در حال جمع‌آوری مزایده‌ها",
  }[state.status] || "در حال دریافت از سامانه ستاد";
  const panelLabel = kind === "tenders" ? "فرآیند مناقصه‌ها" : "فرآیند مزایده‌ها";

  return (
    <section className={"collection-progress " + (state.status === "failed" ? "collection-progress--failed" : "")}>
      <div className="collection-progress__top">
        <div>
          <span className="eyebrow">{panelLabel}</span>
          <strong>{statusLabel}</strong>
        </div>
        <span className="collection-progress__percent">{formatNumber(percent)}٪</span>
        {finished && percent >= 100 && (
          <button
            type="button"
            className="collection-progress__dismiss"
            onClick={onDismiss}
            aria-label="بستن وضعیت جمع‌آوری"
            title="بستن"
          >
            <X size={14} />
          </button>
        )}
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
      <p className="collection-progress__message">
        {isBatch && active && state.current_source_label ? (
          <>
            منبع {formatNumber(state.current_source_index)} از {formatNumber(state.total_sources)}
            {" · "}{state.current_source_label} ({formatNumber(state.current_progress_percent)}٪)
            {state.current_phase === "importing" && " · در حال ذخیره"}
          </>
        ) : state.message}
      </p>
      <div className="collection-progress__metrics">
        {isBatch ? (
          <>
            <span><strong>{formatNumber(state.completed_sources)}</strong> از {formatNumber(state.total_sources)} منبع اجرا شده</span>
            <span><strong>{formatNumber(state.successful_sources)}</strong> منبع موفق</span>
            {active && state.current_source_key && (
              <>
                <span><strong>{formatNumber(state.current_pages_completed)}</strong> / {formatNumber(state.current_total_pages)} صفحه</span>
                <span><strong>{formatNumber(state.current_records_fetched)}</strong> رکورد دریافت‌شده</span>
              </>
            )}
          </>
        ) : (
          <>
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
          </>
        )}
      </div>
      {state.status === "failed" && state.error && (
        <details className="collection-progress__error">
          <summary>نمایش جزئیات خطا</summary>
          <pre>{state.error}</pre>
        </details>
      )}
      {isBatch && state.failed_sources?.length > 0 && (
        <details className="collection-progress__error">
          <summary>{formatNumber(state.failed_sources.length)} منبع ناموفق</summary>
          <ul className="collection-progress__failed-sources">
            {state.failed_sources.map(({ key, label, error }) => (
              <li key={key}><strong>{label}</strong><pre>{error}</pre></li>
            ))}
          </ul>
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

function AuctionScopeFilters({ collectionGroup, categories, onGroupChange, onCategoryChange }) {
  const allTypes = categories.length === 0;
  const hasClearance = allTypes || categories.includes("clearance");
  const groupLabel = categories.length === 1 && hasClearance
    ? GROUP_LABELS.shared
    : collectionGroup === "all" ? "هر دو مجموعه" : GROUP_LABELS[collectionGroup];
  const categoryLabel = allTypes ? "همه انواع" : categories.map((key) => CATEGORY_LABELS[key]).join("، ");

  return (
    <section className="auction-scope" aria-labelledby="auction-scope-title">
      <h2 className="auction-scope__title" id="auction-scope-title">
        <SlidersHorizontal size={17} aria-hidden="true" />
        محدودهٔ مزایده‌ها
      </h2>
      <div className="auction-scope__row">
        <div className="auction-scope__description">
          <h3 id="auction-scope-group">مجموعه آگهی</h3>
          <p id="auction-scope-group-hint">یک مجموعه یا هر دو مجموعه را انتخاب کنید.</p>
        </div>
        <div className="auction-scope__options" role="group" aria-labelledby="auction-scope-group" aria-describedby="auction-scope-group-hint">
          {AUCTION_GROUPS.map(({ key, label }) => (
            <button key={key} type="button" aria-pressed={collectionGroup === key} onClick={() => onGroupChange(key)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="auction-scope__row">
        <div className="auction-scope__description">
          <h3 id="auction-scope-category">نوع مزایده</h3>
          <p id="auction-scope-category-hint">چند نوع را هم‌زمان انتخاب کنید یا «همه» را بزنید.</p>
        </div>
        <div className="auction-scope__options" role="group" aria-labelledby="auction-scope-category" aria-describedby="auction-scope-category-hint">
          {[{ key: "all", label: "همه" }, ...AUCTION_CATEGORIES].map(({ key, label }) => {
            const selected = key === "all" ? allTypes : categories.includes(key);
            return (
              <button key={key} type="button" aria-pressed={selected} onClick={() => onCategoryChange(key)}>
                {selected && <Check size={13} aria-hidden="true" />}
                {label}
              </button>
            );
          })}
        </div>
      </div>
      <footer className="auction-scope__footer">
        <span className="auction-scope__selection"><strong>نمای فعلی</strong> {groupLabel} · {categoryLabel}</span>
        {hasClearance && <span><Info size={14} aria-hidden="true" /> حراج مشترک از تابلوی مرکزی ستاد دریافت می‌شود.</span>}
      </footer>
    </section>
  );
}

export function DetailModal({ record, kind, loading, onClose }) {
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
          ["مجموعه", ({
            executive_agencies: "دستگاه‌های اجرایی",
            amval_tamliki: "سازمان جمع‌آوری و فروش اموال تملیکی",
            shared: "حراج مشترک ستاد",
          })[record.collection_group] || "—"],
          ["دسته مزایده", CATEGORY_LABELS[record.category] || "—"],
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

export default function Dashboard({ kind }) {
  const isTender = kind === "tenders";
  const pageTitle = isTender ? "پایش مناقصه‌ها" : "پایش مزایده‌ها";
  const [collectionGroup, setCollectionGroup] = useState("executive_agencies");
  // An empty selection is the «همه» view.
  const [selectedCategories, setSelectedCategories] = useState(["movable"]);
  const auctionCategory = selectedCategories.length === 1 ? selectedCategories[0] : null;
  const selectedCategoryLabel = CATEGORY_LABELS[auctionCategory] || (
    selectedCategories.length ? "انواع انتخاب‌شده" : "همه انواع"
  );
  const isSharedClearance = !isTender && auctionCategory === "clearance";
  const effectiveCollectionGroup = isSharedClearance ? "shared" : collectionGroup;
  const isAuctionBatch = !isTender && (!auctionCategory || effectiveCollectionGroup === "all");
  const collectionCategory = isAuctionBatch ? "all" : auctionCategory;
  const batchCategories = isAuctionBatch ? selectedCategories : undefined;
  const collectionLabel = isTender ? "مناقصه‌ها" : "مزایده‌ها";
  const collectionTarget = useMemo(() => (
    [kind, collectionCategory, effectiveCollectionGroup, batchCategories]
  ), [kind, collectionCategory, effectiveCollectionGroup, batchCategories]);
  const auctionScope = useMemo(() => ({
    category: "all",
    categories: selectedCategories,
    collection_group: effectiveCollectionGroup,
  }), [selectedCategories, effectiveCollectionGroup]);
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
  const [sortBy, setSortBy] = useState(isTender ? "announcement_at" : "proposal_deadline");
  const [sortDir, setSortDir] = useState(isTender ? "desc" : "asc");
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { params: filterParams, panel: filterPanel } = useListingFilters(setError, !isTender);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [collectionState, setCollectionState] = useState({ status: "idle" });
  const [trackedCollection, setTrackedCollection] = useState(null);
  const [collectionProgressDismissed, setCollectionProgressDismissed] = useState(false);
  const dismissedCollectionRuns = useRef(new Set());
  const lastRefreshedRun = useRef(null);
  const lastNotifiedCollectionRun = useRef(null);
  const lastRequestId = useRef(0);
  const startRequestVersion = useRef(0);
  const [collectionStarting, setCollectionStarting] = useState(false);

  const loadPage = useCallback(async (nextPage = 1) => {
    const requestId = ++lastRequestId.current;
    setLoading(true);
    setError("");
    try {
      const fetchPage = isTender ? getTenders : getAuctions;
      const data = await fetchPage({
        search,
        ...filterParams,
        ...(!isTender ? auctionScope : {}),
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
          "ارتباط با سرور برقرار نشد. از در دسترس بودن سرویس‌ها مطمئن شو.",
      );
    } finally {
      if (requestId === lastRequestId.current) setLoading(false);
    }
  }, [isTender, auctionScope, filterParams, search, sortBy, sortDir, pageSize]);

  useEffect(() => {
    loadPage(1);
  }, [loadPage]);

  useEffect(() => {
    if (trackedCollection) return undefined;
    let active = true;
    const requestVersion = startRequestVersion.current;
    getCollectionStatus(...collectionTarget).then((status) => {
      if (!active || requestVersion !== startRequestVersion.current) return;
      setCollectionState(status);
      if (ACTIVE_STATES.has(status.status)) setTrackedCollection(collectionTarget);
    }).catch(() => {});
    return () => { active = false; };
  }, [collectionTarget, trackedCollection]);

  useEffect(() => {
    if (!trackedCollection || !ACTIVE_STATES.has(collectionState.status)) return undefined;
    let cancelled = false;
    let requestInFlight = false;
    const timer = window.setInterval(async () => {
      if (requestInFlight) return;
      requestInFlight = true;
      try {
        const nextState = await getCollectionStatus(...trackedCollection);
        if (cancelled) return;
        setCollectionState(nextState);
        const completedRunKey = nextState.finished_at || nextState.started_at;
        const finished = ["completed", "completed_with_errors", "failed"].includes(nextState.status);
        if (finished && completedRunKey && lastNotifiedCollectionRun.current !== completedRunKey) {
          lastNotifiedCollectionRun.current = completedRunKey;
          const stored = formatNumber(nextState.records_stored || nextState.totals?.stored || 0);
          const message = nextState.kind === "auction_batch"
            ? nextState.message
            : nextState.status === "completed"
              ? "جمع‌آوری " + collectionLabel + " با موفقیت انجام شد. " + stored + " رکورد ذخیره شد."
              : "جمع‌آوری " + collectionLabel + " ناموفق بود. جزئیات در پنل وضعیت اجرا قابل مشاهده است.";
          notifyToast(nextState.status === "completed" ? "success" : "error", message, { duration: 5500 });
          const hasSavedData = nextState.status !== "failed" || nextState.records_stored > 0;
          if (hasSavedData && lastRefreshedRun.current !== completedRunKey) {
            lastRefreshedRun.current = completedRunKey;
            await loadPage(1);
          }
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
  }, [collectionState.status, trackedCollection, loadPage, collectionLabel]);

  const provinceCount = new Set(result.items.map((item) => item.province).filter(Boolean)).size;
  const organizationCount = new Set(result.items.map((item) => item.organization).filter(Boolean)).size;
  const fourthStat = isTender
    ? new Set(result.items.map((item) => item.type_name).filter(Boolean)).size
    : auctionCategory === "clearance"
      ? result.items.filter((item) => item.has_keyword_match).length
      : result.items.filter((item) => item.state === "PUBLISHED").length;
  const archiveStats = result.archive_stats || {};
  const collectionRunning = ACTIVE_STATES.has(collectionState.status);
  const collectionRunKey = collectionState.finished_at || collectionState.started_at;
  const isCollectionProgressDismissed = collectionProgressDismissed ||
    Boolean(collectionRunKey && dismissedCollectionRuns.current.has(collectionRunKey));

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
      ...(!auctionCategory ? [{
        key: "category", label: "نوع مزایده", sortable: true, sortKey: "category",
        render: (item) => CATEGORY_LABELS[item.category] || item.category,
      }] : []),
      ...(collectionGroup === "all" && !isSharedClearance ? [{
        key: "collection_group", label: "مجموعه", sortable: true, sortKey: "collection_group",
        render: (item) => GROUP_LABELS[item.collection_group] || item.collection_group,
      }] : []),
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
  }, [isTender, auctionCategory, collectionGroup, isSharedClearance]);

  function clearCollectionState() {
    if (collectionStarting || collectionRunning) return;
    setTrackedCollection(null);
    setCollectionState({ status: "idle" });
    setCollectionProgressDismissed(false);
    lastRefreshedRun.current = null;
    lastNotifiedCollectionRun.current = null;
  }

  function handleCategoryChange(category) {
    if (category === "all" && selectedCategories.length === 0) return;
    lastRequestId.current += 1;
    const next = category === "all"
      ? []
      : selectedCategories.includes(category)
        ? selectedCategories.filter((key) => key !== category)
        : [...selectedCategories, category];
    setSelectedCategories(next.length === AUCTION_CATEGORIES.length ? [] : next);
    if (["item_title", "asset_type", "category"].includes(sortBy)) {
      setSortBy("proposal_deadline");
      setSortDir("asc");
    }
    clearCollectionState();
  }

  function handleCollectionGroupChange(nextGroup) {
    if (nextGroup === collectionGroup) return;
    if (!isSharedClearance) lastRequestId.current += 1;
    setCollectionGroup(nextGroup);
    if (sortBy === "collection_group") {
      setSortBy("proposal_deadline");
      setSortDir("asc");
    }
    if (!isSharedClearance) clearCollectionState();
  }

  function handleSearch(event) {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
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
    startRequestVersion.current += 1;
    setTrackedCollection(collectionTarget);
    setCollectionStarting(true);
    setError("");
    setCollectionProgressDismissed(false);
    const toastId = notifyToast(
      "loading",
      "در حال ارسال درخواست جمع‌آوری " + collectionLabel + "...",
      { duration: 0 },
    );
    try {
      const nextState = await startCollection(...collectionTarget);
      setCollectionState((current) => ({
        ...nextState,
        last_updated_at: nextState.last_updated_at ?? current.last_updated_at,
      }));
      notifyToast(
        "info",
        "درخواست جمع‌آوری " + collectionLabel + " ثبت شد؛ نتیجه پس از پایان اجرا اعلام می‌شود.",
        { id: toastId, duration: 4200 },
      );
    } catch (requestError) {
      const message = requestError.response?.data?.detail ||
        ("شروع جمع‌آوری " + collectionLabel + " ناموفق بود.");
      setTrackedCollection(null);
      setError(message);
      notifyToast("error", message, { id: toastId, duration: 6500 });
    } finally {
      setCollectionStarting(false);
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
      notifyToast("error", "دریافت جزئیات آگهی ناموفق بود.");
    } finally {
      setDetailLoading(false);
    }
  }

  const exportParams = listingQueryParams({
    search,
    ...filterParams,
    ...(!isTender ? auctionScope : {}),
    sort_by: sortBy,
    sort_dir: sortDir,
  });
  const exportHref = "/api/" + kind + "/export.xlsx?" + exportParams.toString();

  return (
    <>
      <div className="dashboard-content" id="dashboard">
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
              {isTender && <p>فراخوان‌های مناقصه از زیرسامانه مستقل مناقصه‌های ستاد</p>}
            </div>
            <div className="page-heading__actions">
              <section className="collection-action-card" aria-label="عملیات داده">
                <button
                  className="button button--primary collection-action-card__collect"
                  onClick={handleCollection}
                  disabled={collectionRunning || collectionStarting}
                  aria-label={isTender ? "جمع‌آوری مناقصه‌ها" : "جمع‌آوری داده"}
                >
                  {collectionRunning || collectionStarting ? <LoaderCircle size={16} className="spin" /> : <Play size={16} />}
                  <span>{collectionRunning || collectionStarting
                    ? "در حال اجرا..."
                    : isTender ? "جمع‌آوری مناقصه‌ها" : "جمع‌آوری داده"}</span>
                </button>
                <span
                  className="collection-action-card__last-updated"
                  title={formatLastCollectionUpdate(collectionState.last_updated_at)}
                >
                  {formatLastCollectionUpdate(collectionState.last_updated_at)}
                </span>
              </section>
            </div>
          </section>

          {!isTender && (
            <AuctionScopeFilters
              collectionGroup={collectionGroup}
              categories={selectedCategories}
              onGroupChange={handleCollectionGroupChange}
              onCategoryChange={handleCategoryChange}
            />
          )}
          {!isCollectionProgressDismissed && (
            <CollectionProgress
              state={collectionState}
              kind={kind}
              onDismiss={() => {
                if (collectionRunKey) dismissedCollectionRuns.current.add(collectionRunKey);
                setCollectionProgressDismissed(true);
              }}
            />
          )}

          <section className="stats-grid">
            <StatCard
              icon={isTender ? FileText : Gavel}
              label="رکورد در کل آرشیو"
              value={result.total}
              pageLabel="نتایج با فیلتر فعلی"
              hint={isTender ? "مجموع تمام مناقصه‌های ذخیره‌شده" : "مجموع آگهی‌های ذخیره‌شده در دسته و مجموعه انتخاب‌شده"}
              archiveValue={archiveStats.total}
            />
            <StatCard
              icon={MapPin}
              label="استان در کل آرشیو"
              value={provinceCount}
              hint="تعداد استان‌های متمایز در آرشیو"
              archiveValue={archiveStats.province_count}
              tone="violet"
            />
            <StatCard
              icon={Building2}
              label="سازمان در کل آرشیو"
              value={organizationCount}
              hint="تعداد سازمان‌های متمایز در آرشیو"
              archiveValue={archiveStats.organization_count}
              tone="teal"
            />
            <StatCard
              icon={CheckCircle2}
              label={isTender ? "نوع فراخوان در کل آرشیو" : auctionCategory === "clearance" ? "آگهی مرتبط در کل آرشیو" : "آگهی منتشرشده در کل آرشیو"}
              value={fourthStat}
              hint={isTender ? "تعداد انواع فراخوان متمایز در آرشیو" : auctionCategory === "clearance" ? "تعداد آگهی‌های منطبق با کلیدواژه‌ها" : "تعداد آگهی‌های منتشرشده در آرشیو"}
              archiveValue={isTender ? archiveStats.type_count : auctionCategory === "clearance" ? archiveStats.matched_total : archiveStats.published_count}
              tone="amber"
            />
          </section>

          <ListingTable
            eyebrow="داده‌های استخراج‌شده"
            title={isTender ? "فهرست مناقصه‌ها" : !selectedCategories.length ? "فهرست همه مزایده‌ها" : isSharedClearance ? "فهرست حراج‌های مشترک" : "فهرست مزایده‌های " + selectedCategoryLabel}
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
            headerActions={
              <ExcelExportButton
                href={exportHref}
                filename={isTender ? "setadscope_tenders.xlsx" : "setadscope_auctions.xlsx"}
              />
            }
            advancedSearch={
              <FiltersPanel
                kind={kind}
                options={result.filter_options || {}}
                {...filterPanel}
              />
            }
          />

          <footer className="dashboard-footer">
            <span>SetadScope · پایش داده‌های عمومی معاملات</span>
            <span><CircleDollarSign size={14} /> واحد پول مبالغ تا زمان اعتبارسنجی نمایش داده نمی‌شود</span>
          </footer>
      </div>

      {(selectedRecord || detailLoading) && (
        <DetailModal
          record={selectedRecord}
          kind={kind}
          loading={detailLoading}
          onClose={() => { setSelectedRecord(null); setDetailLoading(false); }}
        />
      )}
    </>
  );
}
