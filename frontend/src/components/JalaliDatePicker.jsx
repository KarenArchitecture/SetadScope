import { useEffect, useRef, useState } from "react";
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight, X } from "lucide-react";

const MONTHS = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
];
const WEEKDAYS = ["ش", "ی", "د", "س", "چ", "پ", "ج"];
const PERSIAN_NUMBER = new Intl.NumberFormat("fa-IR");
const JALALI_LEAP_REMAINDERS = new Set([1, 5, 9, 13, 17, 22, 26, 30]);

function toPersianNumber(value) {
  return PERSIAN_NUMBER.format(value);
}

function jalaliToGregorian(year, month, day) {
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) return null;
  if (month < 1 || month > 12) return null;
  if (month <= 6 && (day < 1 || day > 31)) return null;
  if (month >= 7 && month <= 11 && (day < 1 || day > 30)) return null;
  if (month === 12 && (day < 1 || day > (JALALI_LEAP_REMAINDERS.has(year % 33) ? 30 : 29))) return null;

  let jy = year + 1595;
  let days = -355668 + (365 * jy) + (Math.floor(jy / 33) * 8) + Math.floor((jy % 33 + 3) / 4) + day;
  days += month < 7 ? (month - 1) * 31 : ((month - 7) * 30) + 186;

  let gy = 400 * Math.floor(days / 146097);
  days %= 146097;
  if (days > 36524) {
    gy += 100 * Math.floor((days - 1) / 36524);
    days = (days - 1) % 36524;
    if (days >= 365) days += 1;
  }
  gy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    gy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }

  let gregorianDay = days + 1;
  const leap = (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0;
  const monthLengths = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  let gregorianMonth = 1;
  for (const length of monthLengths) {
    if (gregorianDay <= length) break;
    gregorianDay -= length;
    gregorianMonth += 1;
  }
  return { year: gy, month: gregorianMonth, day: gregorianDay };
}

function gregorianToJalali(year, month, day) {
  const date = new Date(Date.UTC(year, month - 1, day));
  const parts = new Intl.DateTimeFormat("en-US-u-ca-persian-nu-latn", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    timeZone: "UTC",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return {
    year: Number(values.year),
    month: Number(values.month),
    day: Number(values.day),
  };
}

function parseIsoDate(value) {
  if (!value) return null;
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const [, year, month, day] = match.map(Number);
  return gregorianToJalali(year, month, day);
}

function toIsoDate(year, month, day) {
  const date = jalaliToGregorian(year, month, day);
  if (!date) return "";
  return [
    String(date.year).padStart(4, "0"),
    String(date.month).padStart(2, "0"),
    String(date.day).padStart(2, "0"),
  ].join("-");
}

function getTodayJalali() {
  const parts = new Intl.DateTimeFormat("en-US-u-ca-gregory-nu-latn", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Tehran",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return gregorianToJalali(Number(values.year), Number(values.month), Number(values.day));
}

function getMonthLength(year, month) {
  if (month <= 6) return 31;
  if (month <= 11) return 30;
  return jalaliToGregorian(year, 12, 30) ? 30 : 29;
}

function shiftMonth(current, amount) {
  let year = current.year;
  let month = current.month + amount;
  while (month < 1) {
    month += 12;
    year -= 1;
  }
  while (month > 12) {
    month -= 12;
    year += 1;
  }
  return { year, month };
}

function formatJalaliDate(value) {
  const date = parseIsoDate(value);
  if (!date) return "";
  return toPersianNumber(date.year) + "/" +
    toPersianNumber(String(date.month).padStart(2, "0")) + "/" +
    toPersianNumber(String(date.day).padStart(2, "0"));
}

export default function JalaliDatePicker({
  value,
  onChange,
  placeholder = "انتخاب تاریخ شمسی",
  ariaLabel = "انتخاب تاریخ شمسی",
}) {
  const rootRef = useRef(null);
  const selected = parseIsoDate(value);
  const today = getTodayJalali();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState(() => selected || today);

  useEffect(() => {
    if (selected) setView({ year: selected.year, month: selected.month });
  }, [value]);

  useEffect(() => {
    if (!open) return undefined;
    const handlePointerDown = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const handleKeyDown = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const firstDay = jalaliToGregorian(view.year, view.month, 1);
  const weekdayOffset = (new Date(Date.UTC(firstDay.year, firstDay.month - 1, firstDay.day)).getUTCDay() + 1) % 7;
  const monthLength = getMonthLength(view.year, view.month);
  const cells = Array.from({ length: 42 }, (_, index) => {
    const day = index - weekdayOffset + 1;
    return day >= 1 && day <= monthLength ? day : null;
  });

  function chooseDate(day) {
    const nextValue = toIsoDate(view.year, view.month, day);
    if (nextValue) onChange(nextValue);
    setOpen(false);
  }

  function chooseToday() {
    onChange(toIsoDate(today.year, today.month, today.day));
    setView({ year: today.year, month: today.month });
    setOpen(false);
  }

  return (
    <div className="jalali-date-picker" ref={rootRef}>
      <button
        type="button"
        className={"jalali-date-picker__trigger " + (open ? "jalali-date-picker__trigger--open" : "")}
        onClick={() => setOpen((current) => !current)}
        aria-label={ariaLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <CalendarDays size={16} />
        <span className={value ? "jalali-date-picker__value" : "jalali-date-picker__placeholder"}>
          {value ? formatJalaliDate(value) : placeholder}
        </span>
        <ChevronDown size={14} className="jalali-date-picker__trigger-chevron" />
      </button>

      {open && (
        <div className="jalali-calendar" role="dialog" aria-label="تقویم شمسی">
          <div className="jalali-calendar__header">
            <button
              type="button"
              onClick={() => setView((current) => shiftMonth(current, -1))}
              aria-label="ماه قبل"
            >
              <ChevronRight size={17} />
            </button>
            <strong>{MONTHS[view.month - 1]} {toPersianNumber(view.year)}</strong>
            <button
              type="button"
              onClick={() => setView((current) => shiftMonth(current, 1))}
              aria-label="ماه بعد"
            >
              <ChevronLeft size={17} />
            </button>
          </div>

          <div className="jalali-calendar__weekdays">
            {WEEKDAYS.map((day, index) => <span key={day + "-" + index}>{day}</span>)}
          </div>

          <div className="jalali-calendar__days">
            {cells.map((day, index) => {
              if (!day) return <span className="jalali-calendar__empty" key={"empty-" + index} />;
              const isSelected = selected &&
                selected.year === view.year &&
                selected.month === view.month &&
                selected.day === day;
              const isToday = today.year === view.year && today.month === view.month && today.day === day;
              return (
                <button
                  type="button"
                  key={day}
                  className={[
                    "jalali-calendar__day",
                    isSelected ? "jalali-calendar__day--selected" : "",
                    isToday ? "jalali-calendar__day--today" : "",
                  ].filter(Boolean).join(" ")}
                  onClick={() => chooseDate(day)}
                  aria-pressed={Boolean(isSelected)}
                  aria-label={toPersianNumber(day) + " " + MONTHS[view.month - 1] + " " + toPersianNumber(view.year)}
                >
                  {toPersianNumber(day)}
                </button>
              );
            })}
          </div>

          <div className="jalali-calendar__footer">
            <button type="button" onClick={() => { onChange(""); setOpen(false); }}>
              <X size={13} /> پاک کردن
            </button>
            <button type="button" onClick={chooseToday}>امروز</button>
          </div>
        </div>
      )}
    </div>
  );
}
