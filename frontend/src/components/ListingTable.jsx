import { ArrowDown, ArrowLeft, ArrowUp, ChevronLeft, ChevronRight, LoaderCircle, Search, X } from "lucide-react";

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat("fa-IR").format(value);
}

export default function ListingTable({
  eyebrow,
  title,
  tag = "داده خام",
  columns,
  items,
  loading,
  page,
  pages,
  total,
  pageSize,
  onPageChange,
  onPageSizeChange,
  onDetails,
  searchInput,
  onSearchInput,
  onSearch,
  searchPlaceholder,
  error,
  onRetry,
  sortBy,
  sortDir,
  onSort,
  advancedSearch,
  headerActions,
}) {
  const from = total ? (page - 1) * pageSize + 1 : 0;
  const to = Math.min(page * pageSize, total);

  return (
    <section className="data-panel">
      <div className="data-panel__header">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
        </div>
        <div className="data-panel__header-actions">
          {headerActions}
          <span className="raw-tag">{tag}</span>
        </div>
      </div>

      <form className="search-bar" onSubmit={onSearch}>
        <Search size={18} />
        <input
          value={searchInput}
          onChange={(event) => onSearchInput(event.target.value)}
          placeholder={searchPlaceholder}
          aria-label="جست‌وجو در آگهی‌ها"
        />
        {searchInput && (
          <button
            type="button"
            className="search-clear"
            onClick={() => onSearchInput("")}
            aria-label="پاک کردن"
          >
            <X size={16} />
          </button>
        )}
        <button className="button button--primary" type="submit" disabled={loading}>
          جست‌وجو
        </button>
      </form>

      {advancedSearch}

      {error && (
        <div className="error-state">
          <span>{error}</span>
          <button onClick={onRetry}>تلاش مجدد</button>
        </div>
      )}

      <div className="table-wrap">
        <table className="auction-table">
          <thead>
            <tr>
              {columns.map((column) => {
                const active = sortBy === column.sortKey;
                return (
                  <th key={column.key}>
                    {column.sortable ? (
                      <button
                        type="button"
                        className={"table-sort " + (active ? "table-sort--active" : "")}
                        onClick={() => onSort(column.sortKey)}
                        aria-label={"مرتب‌سازی بر اساس " + column.label}
                      >
                        {column.label}
                        {active
                          ? sortDir === "asc"
                            ? <ArrowUp size={13} />
                            : <ArrowDown size={13} />
                          : <ArrowDown size={13} />}
                      </button>
                    ) : column.label}
                  </th>
                );
              })}
              <th><span className="sr-only">جزئیات</span></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length + 1} className="table-message">
                  <LoaderCircle className="spin" /> در حال دریافت اطلاعات...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={columns.length + 1} className="table-message">
                  رکوردی با این جست‌وجو و فیلترها پیدا نشد.
                </td>
              </tr>
            ) : items.map((item) => (
              <tr key={item.row_key || item.id}>
                {columns.map((column) => (
                  <td key={column.key} className={column.className || ""}>
                    {column.render
                      ? column.render(item)
                      : (item[column.key] ?? "—")}
                  </td>
                ))}
                <td>
                  <button className="row-action" onClick={() => onDetails(item.id, item)}>
                    جزئیات <ArrowLeft size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <footer className="table-footer">
        <span>نمایش {formatNumber(from)} تا {formatNumber(to)} از {formatNumber(total)} رکورد</span>
        <div className="table-footer__controls">
          <label className="page-size-control">
            تعداد در صفحه
            <select value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
              <option value={20}>۲۰</option>
              <option value={50}>۵۰</option>
              <option value={100}>۱۰۰</option>
            </select>
          </label>
          <div className="pagination">
            <button
              aria-label="صفحه قبل"
              disabled={loading || page <= 1}
              onClick={() => onPageChange(page - 1)}
            >
              <ChevronRight size={17} />
            </button>
            <span>صفحه {formatNumber(page)} از {formatNumber(pages)}</span>
            <button
              aria-label="صفحه بعد"
              disabled={loading || page >= pages}
              onClick={() => onPageChange(page + 1)}
            >
              <ChevronLeft size={17} />
            </button>
          </div>
        </div>
      </footer>
    </section>
  );
}
