import { useEffect, useRef, useState } from "react";
import { CalendarDays, X } from "lucide-react";
import { getCollectionStatus, startCollection } from "../services/api";
import ExcelExportButton from "../components/ExcelExportButton";
import "./QuickActions.css";

const report = "/api/auctions/export.xlsx?category=all&collection_group=all&today_only=true&matched_only=false&sort_by=announcement_at&sort_dir=desc";
const storageKey = "setadscope-quick-auctions";

export default function QuickActions() {
  const modal = useRef(null);
  const starting = useRef(false);
  const [run, setRun] = useState(() => sessionStorage.getItem(storageKey));
  const [state, setState] = useState(null);
  const [error, setError] = useState("");
  const finished = ["completed", "completed_with_errors"].includes(state?.status);

  useEffect(() => {
    if (!run || finished) return;
    let active = true;
    let timer;
    async function poll() {
      try {
        const next = await getCollectionStatus("auctions", "all", "all");
        if (!active) return;
        if (next.started_at !== run) {
          sessionStorage.removeItem(storageKey);
          setRun(null);
          setError("اجرای قبلی دیگر در دسترس نیست. دوباره شروع کنید.");
          return;
        }
        setError("");
        setState(next);
      } catch {
        if (active) setError("ارتباط قطع شد. دریافت وضعیت دوباره تلاش می‌شود.");
      }
      if (active) timer = setTimeout(poll, 1200);
    }
    poll();
    return () => { active = false; clearTimeout(timer); };
  }, [run, finished]);

  async function open() {
    modal.current.showModal();
    if (starting.current || (run && !finished)) return;
    starting.current = true;
    setError("");
    setState(null);
    try {
      const next = await startCollection("auctions", "all", "all");
      sessionStorage.setItem(storageKey, next.started_at);
      setState(next);
      setRun(next.started_at);
    } catch (e) {
      setError(e.response?.data?.detail || "شروع جمع‌آوری ناموفق بود.");
      setRun(null);
    } finally { starting.current = false; }
  }

  return <section className="dashboard-content quick-actions">
    <h1>دسترسی سریع</h1>
    <div className="quick-grid"><button className="quick-card" onClick={open}>
      <CalendarDays size={42} aria-hidden="true" />
      <strong>مزایده‌های امروز</strong>
      <span>جمع‌آوری همه انواع مزایده و دانلود اکسل به ترتیب ساعت اعلام</span>
    </button></div>
    <dialog ref={modal} aria-labelledby="quick-title">
      <button className="quick-close" aria-label="بستن" onClick={() => modal.current.close()}><X size={18}/></button>
      <h2 id="quick-title">گزارش مزایده‌های امروز</h2>
      <p role="status">{error || state?.message || "در حال شروع جمع‌آوری…"}</p>
      {state && <><progress aria-label="پیشرفت جمع‌آوری" max="100" value={state.overall_progress_percent}/>
        <p>{state.completed_sources} از {state.total_sources} منبع · {state.overall_progress_percent}٪</p></>}
      {state?.failed_sources?.map(source => <p key={source.key}>{source.label} · {source.error}</p>)}
      {finished && <><p>{state.failed_sources.length ? "گزارش ناقص است. " : ""}اکسل شامل آگهی‌های ثبت‌شده با تاریخ اعلام امروز به وقت تهران است.</p>
        <ExcelExportButton key={run} autoStart={sessionStorage.getItem(storageKey) === run} onAutoStart={() => sessionStorage.removeItem(storageKey)} href={report} filename="setadscope_today_auctions.xlsx"/></>}
    </dialog>
  </section>;
}
