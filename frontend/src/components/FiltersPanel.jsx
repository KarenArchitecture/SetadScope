import { CalendarDays, ChevronDown, Filter, RotateCcw } from "lucide-react";
import DeadlineStatusSelect from "./DeadlineStatusSelect";
import JalaliDatePicker from "./JalaliDatePicker";

function displayState(value) {
  return value === "PUBLISHED" ? "منتشر شده" : value;
}

function retainSelection(values, selected) {
  return selected && !values.includes(selected) ? [selected, ...values] : values;
}

function FilterField({ label, children, className = "" }) {
  return (
    <label className={["filter-field", className].filter(Boolean).join(" ")}>
      <span>{label}</span>
      {children}
    </label>
  );
}

export default function FiltersPanel({
  kind,
  showCollection = false,
  filters,
  options,
  onChange,
  onApply,
  onReset,
  isOpen,
  onToggle,
  activeCount,
  canReset,
  matchedOnly,
  onMatchedOnlyChange,
  todayOnly,
  onTodayOnlyChange,
}) {
  const showTenderFilters = kind === "tenders" || kind === "all";
  const showAuctionFilters = kind !== "tenders";
  const provinceOptions = retainSelection(options.provinces || [], filters.province);
  const cityOptions = retainSelection(
    (options.cities || []).filter(({ province }) => province === filters.province).map(({ city }) => city),
    filters.city,
  );
  const stateOptions = retainSelection(options.states || [], filters.state);
  const typeOptions = retainSelection(options.types || [], filters.type_name);

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
                  ? new Intl.NumberFormat("fa-IR").format(activeCount) + " فیلتر فعال"
                  : "استان، شهر، وضعیت مهلت و بازه‌های زمانی"}
              </small>
            </span>
          </span>
          <span className="filters-panel__toggle-action">
            {isOpen ? "بستن جست‌وجو" : "نمایش جست‌وجو"}
            <ChevronDown className={isOpen ? "filters-panel__chevron filters-panel__chevron--open" : "filters-panel__chevron"} size={17} />
          </span>
        </button>
        <div className="filters-panel__quick-actions">
          <label className="filters-panel__match">
            <input
              type="checkbox"
              checked={matchedOnly}
              onChange={(event) => onMatchedOnlyChange(event.target.checked)}
            />
            فقط آگهی‌های مرتبط
          </label>
          <label className="filters-panel__match">
            <input
              type="checkbox"
              checked={todayOnly}
              onChange={(event) => onTodayOnlyChange(event.target.checked)}
            />
            فقط آگهی‌های امروز
          </label>
          <button type="button" className="filters-reset" onClick={onReset} disabled={!canReset} title="حذف تمام فیلترهای انتخابی و اعمال‌شده">
            <RotateCcw size={14} /> حذف فیلترها
          </button>
        </div>
      </header>

      <div className="filters-panel__collapsible" aria-hidden={!isOpen} inert={!isOpen}>
        <div className="filters-panel__collapsible-content">
          <div className="filters-panel__body">
            <div className={"filters-grid " + (kind === "tenders" ? "filters-grid--tenders" : "filters-grid--auctions")}>
              {showCollection && (
                <FilterField label="مجموعه آگهی">
                  <select value={filters.collection_group} onChange={(event) => onChange("collection_group", event.target.value)}>
                    <option value="">همه مجموعه‌ها</option>
                    {(options.collection_groups || []).map(({ value, label }) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </FilterField>
              )}

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

              <FilterField label="وضعیت مهلت">
                <DeadlineStatusSelect
                  value={filters.status}
                  onChange={(value) => onChange("status", value)}
                />
              </FilterField>

              <FilterField label="وضعیت آگهی">
                <select value={filters.state} onChange={(event) => onChange("state", event.target.value)}>
                  <option value="">همه وضعیت‌ها</option>
                  {stateOptions.map((value) => <option key={value} value={value}>{displayState(value)}</option>)}
                </select>
              </FilterField>

              {showTenderFilters && (
                <FilterField label="نوع فراخوان">
                  <select value={filters.type_name} onChange={(event) => onChange("type_name", event.target.value)}>
                    <option value="">همه انواع</option>
                    {typeOptions.map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                </FilterField>
              )}
              {showAuctionFilters && (
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
                  بازه تاریخ اعلام آگهی
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

              {showTenderFilters && (
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
            <span>فیلترها روی کل آرشیو اعمال می‌شوند.</span>
            <button type="button" className="button button--primary" onClick={onApply}>
              <Filter size={15} /> اعمال فیلترها
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
