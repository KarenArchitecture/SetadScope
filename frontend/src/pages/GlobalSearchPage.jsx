import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import ListingTable from "../components/ListingTable";
import ExcelExportButton from "../components/ExcelExportButton";
import FiltersPanel from "../components/FiltersPanel";
import useListingFilters from "../hooks/useListingFilters";
import { notifyToast } from "../utils/toast";
import { defaultListing, listingByKey, listingTypes } from "../listingTypes";
import { getGlobalSearch, listingQueryParams } from "../services/api";
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

function TypeBadge({ kind, label }) {
  const Icon = listingByKey[kind]?.badgeIcon;
  return (
    <span className={"global-result-type global-result-type--" + kind}>
      {Icon && <Icon size={13} />}
      {label || listingByKey[kind]?.label || kind}
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
  const [detailType, setDetailType] = useState(defaultListing);
  const { Details } = detailType;
  const activeType = listingByKey[kind];
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
      render: (item) => <TypeBadge kind={item.record_type} label={item.record_type_label} />,
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
    ...((!activeType || activeType.showDocumentsDeadline) ? [{
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
  ], [activeType]);

  async function openDetails(id, item) {
    const listing = listingByKey[item.record_type];
    if (!listing) return;
    setSelectedRecord(null);
    setDetailType(listing);
    setDetailLoading(true);
    try {
      const record = await listing.getDetails(id);
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
    const nextType = listingByKey[nextKind];
    if (nextType?.excludedFilters?.length) resetFields(nextType.excludedFilters);
    if (nextType && !nextType.showDocumentsDeadline && sortBy === "documents_deadline_at") {
      setSortBy("announcement_at");
      setSortDir("desc");
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
                  ? <>نتایج جست‌وجو برای <strong>«{query}»</strong> در آگهی‌های ثبت‌شده</>
                  : "جدیدترین آگهی‌های ثبت‌شده در همه منابع"}
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
            {listingTypes.map(({ key, page, title }) => (
              <button key={key} type="button" className={kind === key ? "is-active" : ""} onClick={() => changeKind(key)}>
                {title} <span>{formatNumber(summary[page] ?? 0)}</span>
              </button>
            ))}
          </section>

          <ListingTable
            eyebrow="پایگاه یکپارچه معاملات"
            title={activeType ? "تمام " + activeType.title : "فهرست همه آگهی‌ها"}
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
                kind={activeType?.page ?? "all"}
                options={result.filter_options || {}}
                showCollection={activeType?.showCollection ?? true}
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
        <Details
          record={selectedRecord}
          kind={detailType.page}
          loading={detailLoading}
          onClose={() => { setSelectedRecord(null); setDetailLoading(false); }}
        />
      )}
    </>
  );
}
