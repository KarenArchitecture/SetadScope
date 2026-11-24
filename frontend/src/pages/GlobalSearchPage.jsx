import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Building2, Gavel, Search as SearchIcon } from "lucide-react";
import ListingTable from "../components/ListingTable";
import ExcelExportButton from "../components/ExcelExportButton";
import FiltersPanel from "../components/FiltersPanel";
import useListingFilters from "../hooks/useListingFilters";
import { notifyToast } from "../utils/toast";
import { DetailModal } from "./Dashboard";
import { getAuctionById, getGlobalSearch, getTenderById, listingQueryParams } from "../services/api";
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

export default function GlobalSearchPage({ query, onQueryChange }) {
  const [searchInput, setSearchInput] = useState(query);
  const [kind, setKind] = useState("all");
  const [sortBy, setSortBy] = useState("announcement_at");
  const [sortDir, setSortDir] = useState("desc");
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({
    items: [],
    total: 0,
    pages: 0,
    summary: { all: 0, auctions: 0, tenders: 0 },
    archive_summary: { all: 0, auctions: 0, tenders: 0 },
    filter_options: { collection_groups: [], provinces: [] },
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { params: filterParams, panel: filterPanel, resetFields } = useListingFilters(setError);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [detailKind, setDetailKind] = useState("auctions");
  const [detailLoading, setDetailLoading] = useState(false);
  const lastRequestId = useRef(0);

  const loadPage = useCallback(async (nextPage = 1) => {
    const requestId = ++lastRequestId.current;
    setLoading(true);
    setError("");
    try {
      const data = await getGlobalSearch({
        search: query,
        kind,
        ...filterParams,
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
        "دریافت نتایج جست‌وجوی سراسری ناموفق بود. اتصال به سرور را بررسی کن.",
      );
    } finally {
      if (requestId === lastRequestId.current) setLoading(false);
    }
  }, [query, kind, filterParams, sortBy, sortDir, pageSize]);

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
      label: "دسته / نوع فراخوان",
      sortable: true,
      sortKey: "category",
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
    { key: "province", label: "استان", sortable: true, sortKey: "province" },
    { key: "city", label: "شهر", sortable: true, sortKey: "city" },
    {
      key: "announcement_at",
      label: "تاریخ اعلام",
      sortable: true,
      sortKey: "announcement_at",
      className: "date-cell",
      render: (item) => formatDate(item.announcement_at),
    },
    ...(kind !== "auction" ? [{
      key: "documents_deadline_at",
      label: "مهلت اسناد",
      sortable: true,
      sortKey: "documents_deadline_at",
      className: "date-cell",
      render: (item) => formatDate(item.documents_deadline_at),
    }] : []),
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
      sortable: true,
      sortKey: "state",
      render: (item) => (
        <span className={"state-pill " + (item.state === "PUBLISHED" ? "state-pill--published" : "")}>
          {displayState(item.state)}
        </span>
      ),
    },
  ], [kind]);

  async function openDetails(id, item) {
    setSelectedRecord(null);
    setDetailKind(item.record_type === "tender" ? "tenders" : "auctions");
    setDetailLoading(true);
    try {
      const record = item.record_type === "tender"
        ? await getTenderById(id)
        : await getAuctionById(id);
      setSelectedRecord(record);
    } catch {
      setError("دریافت جزئیات این معامله ناموفق بود.");
      notifyToast("error", "دریافت جزئیات این معامله ناموفق بود.");
    } finally {
      setDetailLoading(false);
    }
  }

  function submitSearch(event) {
    event.preventDefault();
    const term = searchInput.trim();
    setSearchInput(term);
    if (term === query) loadPage(1);
    else onQueryChange(term);
  }

  function changeSearchInput(value) {
    setSearchInput(value);
    if (!value && query) onQueryChange("");
  }

  function changeKind(nextKind) {
    if (kind === nextKind) return;
    setKind(nextKind);
    if (nextKind === "tender") {
      resetFields(["collection_group", "price_min", "price_max"]);
    }
    if (nextKind === "auction") {
      resetFields(["type_name", "documents_deadline_from", "documents_deadline_to"]);
      if (sortBy === "documents_deadline_at") {
        setSortBy("announcement_at");
        setSortDir("desc");
      }
    }
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

  const summary = result.summary || { all: 0, auctions: 0, tenders: 0 };
  const archiveSummary = result.archive_summary || { all: 0, auctions: 0, tenders: 0 };
  const exportParams = listingQueryParams({
    search: query,
    kind,
    ...filterParams,
    sort_by: sortBy,
    sort_dir: sortDir,
  });
  const exportHref = "/api/search/export.xlsx?" + exportParams.toString();

  return (
    <>
      <div className="dashboard-content global-search-content" id="global-search">
          <section className="page-heading global-search-heading">
            <div>
              <h1>همه آگهی‌ها</h1>
              <p>
                {query
                  ? <>نتایج جست‌وجو برای <strong>«{query}»</strong> در مزایده‌ها و مناقصه‌ها</>
                  : "جدیدترین معاملات ثبت‌شده در تمام منابع مزایده و مناقصه"}
              </p>
            </div>
            <div className="global-search-total">
              <strong>{formatNumber(archiveSummary.all)}</strong>
              <span>رکورد در کل آرشیو</span>
              <small>نتیجه در نمای فعلی: {formatNumber(result.total)}</small>
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
            headerActions={
              <ExcelExportButton
                href={exportHref}
                filename="setadscope_global.xlsx"
              />
            }
            advancedSearch={
              <FiltersPanel
                kind={kind === "all" ? "all" : kind + "s"}
                options={result.filter_options || {}}
                showCollection={kind !== "tender"}
                {...filterPanel}
              />
            }
            searchInput={searchInput}
            onSearchInput={changeSearchInput}
            onSearch={submitSearch}
            searchPlaceholder="جست‌وجو در عنوان، شرح، شماره یا سازمان آگهی..."
          />

          <footer className="dashboard-footer">
            <span>SetadScope · جست‌وجوی یکپارچه داده‌های عمومی معاملات</span>
            <span><SearchIcon size={14} /> جست‌وجو در عنوان، شرح، شماره، سازمان و موقعیت مکانی</span>
          </footer>
      </div>

      {(selectedRecord || detailLoading) && (
        <DetailModal
          record={selectedRecord}
          kind={detailKind}
          loading={detailLoading}
          onClose={() => { setSelectedRecord(null); setDetailLoading(false); }}
        />
      )}
    </>
  );
}
