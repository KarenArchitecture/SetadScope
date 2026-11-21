import { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, Gavel, RotateCcw, Search as SearchIcon } from "lucide-react";
import ListingTable from "../components/ListingTable";
import Sidebar from "../components/Sidebar";
import ThemeToggle from "../components/ThemeToggle";
import GlobalSearchBar from "../components/GlobalSearchBar";
import { DetailModal } from "./Dashboard";
import { getAuctionById, getGlobalSearch, getTenderById } from "../services/api";
import "./Dashboard.css";
import "../styles/redesign.css";
import "./GlobalSearchPage.css";

const PAGE_SIZE = 20;

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

function remainingTime(value) {
  if (!value) return "نامشخص";
  const difference = new Date(value).getTime() - Date.now();
  if (!Number.isFinite(difference)) return "نامشخص";
  if (difference <= 0) return "مهلت تمام شده";
  const days = Math.floor(difference / 86400000);
  const hours = Math.floor((difference % 86400000) / 3600000);
  if (days > 0) return formatNumber(days) + " روز باقی‌مانده";
  if (hours > 0) return formatNumber(hours) + " ساعت باقی‌مانده";
  return "کمتر از یک ساعت";
}

function displayState(value) {
  return value === "PUBLISHED" ? "منتشر شده" : (value || "نامشخص");
}

function TypeBadge({ kind }) {
  return (
    <span className={"global-result-type global-result-type--" + kind}>
      {kind === "auction" ? <Gavel size={13} /> : <Building2 size={13} />}
      {kind === "auction" ? "مزایده" : "مناقصه"}
    </span>
  );
}

export default function GlobalSearchPage({
  onNavigate,
  theme,
  onThemeToggle,
  sidebarCollapsed,
  onSidebarToggle,
}) {
  const initialQuery = new URLSearchParams(window.location.search).get("q") || "";
  const [query] = useState(initialQuery);
  const [kind, setKind] = useState("all");
  const [source, setSource] = useState("");
  const [category, setCategory] = useState("");
  const [province, setProvince] = useState("");
  const [status, setStatus] = useState("all");
  const [matchedOnly, setMatchedOnly] = useState(false);
  const [sortBy, setSortBy] = useState("announcement_at");
  const [sortDir, setSortDir] = useState("desc");
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({
    items: [],
    total: 0,
    pages: 0,
    summary: { all: 0, auctions: 0, tenders: 0 },
    filter_options: { sources: [], provinces: [], categories: [] },
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadPage = useCallback(async (nextPage = 1) => {
    setLoading(true);
    setError("");
    try {
      const data = await getGlobalSearch({
        search: query,
        kind,
        source,
        ...(kind === "auction" ? { category } : {}),
        province,
        status,
        matched_only: matchedOnly,
        sortBy,
        sortDir,
        page: nextPage,
        pageSize,
      });
      setResult(data);
      setPage(data.page);
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
        "دریافت نتایج جست‌وجوی سراسری ناموفق بود. اتصال Backend را بررسی کن.",
      );
    } finally {
      setLoading(false);
    }
  }, [query, kind, source, category, province, status, matchedOnly, sortBy, sortDir, pageSize]);

  useEffect(() => {
    loadPage(1);
  }, [loadPage]);

  const columns = useMemo(() => [
    {
      key: "title",
      label: "عنوان معامله",
      sortable: true,
      sortKey: "title",
      render: (item) => (
        <div className="auction-title-cell global-result-title">
          <strong>{item.title || "بدون عنوان"}</strong>
          <span>شماره: {item.record_number || "—"}</span>
          {item.has_keyword_match && (
            <small className="global-result-match">مرتبط با کلیدواژه‌ها</small>
          )}
        </div>
      ),
    },
    {
      key: "record_type",
      label: "نوع معامله",
      sortable: true,
      sortKey: "record_type",
      render: (item) => <TypeBadge kind={item.record_type} />,
    },
    {
      key: "category_label",
      label: "دسته",
      render: (item) => item.category_label,
    },
    {
      key: "source_label",
      label: "منبع",
      sortable: true,
      sortKey: "source",
      render: (item) => <span className="global-result-source">{item.source_label}</span>,
    },
    {
      key: "organization",
      label: "سازمان برگزارکننده",
      sortable: true,
      sortKey: "organization",
    },
    {
      key: "province",
      label: "استان / شهر",
      sortable: true,
      sortKey: "province",
      render: (item) => (
        <div className="global-result-location">
          <strong>{item.province || "—"}</strong>
          <span>{item.city || "—"}</span>
        </div>
      ),
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
      key: "deadline_at",
      label: "مهلت پیشنهاد",
      sortable: true,
      sortKey: "deadline_at",
      render: (item) => (
        <div className="deadline-cell">
          <strong>{remainingTime(item.deadline_at)}</strong>
          <span>{formatDate(item.deadline_at)}</span>
        </div>
      ),
    },
    {
      key: "base_total_price",
      label: "مبلغ پایه",
      sortable: true,
      sortKey: "base_total_price",
      className: "numeric-cell",
      render: (item) => item.base_total_price == null
        ? "—"
        : formatNumber(item.base_total_price) + (item.money_unit === "IRR" ? " ریال" : ""),
    },
    {
      key: "state",
      label: "وضعیت",
      render: (item) => (
        <span className={"state-pill " + (item.state === "PUBLISHED" ? "state-pill--published" : "")}>
          {displayState(item.state)}
        </span>
      ),
    },
  ], []);

  async function openDetails(id, item) {
    setSelectedRecord(null);
    setDetailLoading(true);
    try {
      const record = item.record_type === "tender"
        ? await getTenderById(id)
        : await getAuctionById(id);
      setSelectedRecord(record);
    } catch {
      setError("دریافت جزئیات این معامله ناموفق بود.");
    } finally {
      setDetailLoading(false);
    }
  }

  function changeKind(nextKind) {
    if (kind === nextKind) return;
    setKind(nextKind);
    setSource("");
    setCategory("");
    setPage(1);
  }

  function changeSort(key) {
    if (sortBy === key) {
      setSortDir((current) => current === "asc" ? "desc" : "asc");
    } else {
      setSortBy(key);
      setSortDir(key === "announcement_at" || key === "deadline_at" ? "desc" : "asc");
    }
    setPage(1);
  }

  function resetFilters() {
    setSource("");
    setCategory("");
    setProvince("");
    setStatus("all");
    setMatchedOnly(false);
    setPage(1);
  }

  const summary = result.summary || { all: 0, auctions: 0, tenders: 0 };
  const options = result.filter_options || { sources: [], provinces: [], categories: [] };
  const sourceOptions = (options.sources || []).filter((item) => (
    kind === "all" ||
    (kind === "auction" && item.value !== "setad_tender") ||
    (kind === "tender" && item.value === "setad_tender")
  ));
  const canReset = Boolean(source || category || province || status !== "all" || matchedOnly);

  return (
    <div className={"app-shell " + (sidebarCollapsed ? "app-shell--collapsed" : "")}>
      <Sidebar page="search" onNavigate={onNavigate} collapsed={sidebarCollapsed} onToggle={onSidebarToggle} />
      <main className="main-content" id="global-search">
        <header className="topbar">
          <div className="topbar__breadcrumb">SetadScope <span>‹</span> جست‌وجوی سراسری</div>
          <GlobalSearchBar onNavigate={onNavigate} initialQuery={query} />
          <div className="topbar__actions">
            <ThemeToggle theme={theme} onToggle={onThemeToggle} />
          </div>
        </header>

        <div className="dashboard-content global-search-content">
          <section className="page-heading global-search-heading">
            <div>
              <span className="eyebrow">جست‌وجو در تمام منابع داده</span>
              <h1>جست‌وجوی سراسری معاملات</h1>
              <p>
                {query
                  ? <>نتایج جست‌وجو برای <strong>«{query}»</strong> در مزایده‌ها و مناقصه‌ها</>
                  : "جدیدترین معاملات ثبت‌شده در تمام منابع مزایده و مناقصه"}
              </p>
            </div>
            <div className="global-search-total">
              <strong>{formatNumber(summary.all)}</strong>
              <span>نتیجه منطبق با جست‌وجو و فیلترها</span>
            </div>
          </section>

          <section className="global-search-tabs" aria-label="نوع معامله">
            <button type="button" className={kind === "all" ? "is-active" : ""} onClick={() => changeKind("all")}>
              همه معاملات <span>{formatNumber(summary.all)}</span>
            </button>
            <button type="button" className={kind === "auction" ? "is-active" : ""} onClick={() => changeKind("auction")}>
              مزایده‌ها <span>{formatNumber(summary.auctions)}</span>
            </button>
            <button type="button" className={kind === "tender" ? "is-active" : ""} onClick={() => changeKind("tender")}>
              مناقصه‌ها <span>{formatNumber(summary.tenders)}</span>
            </button>
          </section>

          <section className="global-search-filterbar" aria-label="فیلتر نتایج جست‌وجو">
            <label>
              <span>منبع آگهی</span>
              <select value={source} onChange={(event) => { setSource(event.target.value); setPage(1); }}>
                <option value="">همه منابع</option>
                {sourceOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
            {kind === "auction" && (
              <label>
                <span>دسته مزایده</span>
                <select value={category} onChange={(event) => { setCategory(event.target.value); setPage(1); }}>
                  <option value="">همه دسته‌ها</option>
                  {(options.categories || []).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
            )}
            <label>
              <span>استان</span>
              <select value={province} onChange={(event) => { setProvince(event.target.value); setPage(1); }}>
                <option value="">همه استان‌ها</option>
                {(options.provinces || []).map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label>
              <span>وضعیت مهلت</span>
              <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
                <option value="all">همه وضعیت‌ها</option>
                <option value="active">دارای مهلت</option>
                <option value="archive">مهلت تمام‌شده</option>
              </select>
            </label>
            <label className="global-search-match">
              <input type="checkbox" checked={matchedOnly} onChange={(event) => { setMatchedOnly(event.target.checked); setPage(1); }} />
              فقط آگهی‌های مرتبط
            </label>
            <button type="button" className="global-search-reset" onClick={resetFilters} disabled={!canReset}>
              <RotateCcw size={14} /> پاک کردن فیلترها
            </button>
          </section>

          <ListingTable
            eyebrow="پایگاه یکپارچه معاملات"
            title={kind === "auction" ? "تمام مزایده‌ها" : kind === "tender" ? "تمام مناقصه‌ها" : "تمام مزایده‌ها و مناقصه‌ها"}
            tag="جست‌وجوی یکپارچه"
            columns={columns}
            items={result.items}
            loading={loading}
            page={page}
            pages={result.pages}
            total={result.total}
            pageSize={pageSize}
            onPageChange={loadPage}
            onPageSizeChange={(nextSize) => { setPage(1); setPageSize(nextSize); }}
            onDetails={openDetails}
            error={error}
            onRetry={() => loadPage(page)}
            sortBy={sortBy}
            sortDir={sortDir}
            onSort={changeSort}
            hideSearch
          />

          <footer className="dashboard-footer">
            <span>SetadScope · جست‌وجوی یکپارچه داده‌های عمومی معاملات</span>
            <span><SearchIcon size={14} /> جست‌وجو در عنوان، شرح، شماره، سازمان و موقعیت مکانی</span>
          </footer>
        </div>
      </main>

      {(selectedRecord || detailLoading) && (
        <DetailModal
          record={selectedRecord}
          kind={selectedRecord?.source_tender_id ? "tenders" : "auctions"}
          loading={detailLoading}
          onClose={() => { setSelectedRecord(null); setDetailLoading(false); }}
        />
      )}
    </div>
  );
}
