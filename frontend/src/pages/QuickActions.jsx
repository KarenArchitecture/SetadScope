import { useEffect, useRef, useState } from "react";
import { CalendarDays, MapPin, Minus, X } from "lucide-react";
import { quickRequest } from "../services/api";
import ExcelExportButton from "../components/ExcelExportButton";
import "./QuickActions.css";

const actions = {
  auctions: { title: "مزایده‌های امروز", icon: CalendarDays, text: "جمع‌آوری همه انواع مزایده و دانلود اکسل به ترتیب ساعت اعلام", filters: "category=all&collection_group=all&today_only=true" },
  tenders: { title: "مناقصه‌های گلستان", icon: MapPin, text: "دانلود مناقصه‌های استان گلستان از جدیدترین تاریخ اعلام", filters: "province=" + encodeURIComponent("گلستان") },
};
const key = "setadscope.quickRun";
const fa = value => Number(value || 0).toLocaleString("fa-IR");

export default function QuickActions({ visible }) {
  const modal = useRef(null);
  const [job, setJob] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(key)); } catch { return null; }
  });
  const [mini, setMini] = useState(Boolean(job));
  const [state, setState] = useState(null);
  const [error, setError] = useState("");
  const [exportDone, setExportDone] = useState(false);
  const [stopping, setStopping] = useState(false);
  const terminal = ["completed", "completed_with_errors", "cancelled"].includes(state?.status);
  const action = actions[job?.kind];
  const starting = useRef(false);
  const confirmation = useRef(null);

  useEffect(() => {
    if (!job?.id || terminal) return;
    let alive = true;
    let timer;
    async function poll() {
      try {
        const next = await quickRequest(job.kind, "status");
        if (!alive) return;
        if (next.started_at !== job.id) {
          setState({ status: "cancelled", message: "اجرای قبلی پایان یافته یا سرور بازنشانی شده است." });
          sessionStorage.removeItem(key);
          return;
        }
        setState(next);
        setError("");
        if (next.status === "cancelled") sessionStorage.removeItem(key);
      } catch { if (alive) setError("دریافت وضعیت دوباره تلاش می‌شود."); }
      if (alive) timer = setTimeout(poll, 900);
    }
    poll();
    return () => { alive = false; clearTimeout(timer); };
  }, [job, terminal]);

  function restore() {
    setMini(false);
    modal.current.showModal();
  }

  async function start(kind) {
    restore();
    if (job || starting.current) return;
    starting.current = true;
    setJob({ kind });
    setState(null); setError(""); setExportDone(false); setStopping(false);
    try {
      const next = await quickRequest(kind, "run");
      const current = { kind, id: next.started_at };
      sessionStorage.setItem(key, JSON.stringify(current));
      setState(next); setJob(current);
    } catch (e) {
      setError(e.response?.data?.detail || "شروع عملیات ناموفق بود.");
      setState({status:"cancelled"});
    } finally { starting.current = false; }
  }

  useEffect(() => {
    if (stopping && terminal) {
      modal.current.close(); setMini(false); setJob(null); setState(null); setStopping(false);
      sessionStorage.removeItem(key);
    }
  }, [stopping, terminal]);

  async function close(confirmed = false) {
    if (starting.current || stopping) return;
    if (job && !exportDone && state?.status !== "cancelled") {
      if (confirmed !== true) {
        confirmation.current.showModal();
        return;
      }
      if (!terminal) {
        setStopping(true);
        try {
          await quickRequest(job.kind, "stop", job.id);
          return;
        } catch { setStopping(false); setError("درخواست توقف ارسال نشد."); return; }
      }
    }
    modal.current.close();
    setMini(false); setJob(null); setState(null); setStopping(false);
    sessionStorage.removeItem(key);
  }

  return <div className="quick-actions">
    {visible && <section className="dashboard-content"><h1>دسترسی سریع</h1>
      <div className="quick-grid">{Object.entries(actions).map(([kind, item]) =>
        <button key={kind} className="quick-card" disabled={job && job.kind !== kind} onClick={() => start(kind)}>
          <item.icon size={42}/><strong>{item.title}</strong><span>{item.text}</span>
        </button>)}</div></section>}
    {mini && action && <button className="quick-mini" onClick={restore}>{action.title} · {fa(state?.overall_progress_percent)}٪</button>}
    <dialog ref={modal} aria-labelledby="quick-title" onCancel={e => { e.preventDefault(); close(); }}>
      <button className="quick-close" disabled={starting.current || stopping} onClick={close} aria-label="بستن"><X size={18}/></button>
      <button className="quick-close" onClick={() => { modal.current.close(); setMini(true); }} aria-label="کوچک کردن"><Minus size={18}/></button>
      <h2 id="quick-title">{action?.title}</h2>
      <p role="status">{error || (stopping && "در حال توقف عملیات…") || state?.message || "در حال شروع عملیات…"}</p>
      {state?.reused_sources > 0 && <p>{fa(state.reused_sources)} منبع در ۱۵ دقیقهٔ اخیر به‌روز شده و از دادهٔ ذخیره‌شده استفاده شد.</p>}
      {state?.total_sources > 0 && <><progress max="100" value={state.overall_progress_percent}/><p>{fa(state.completed_sources)} از {fa(state.total_sources)} منبع · {fa(state.overall_progress_percent)}٪</p></>}
      {state?.failed_sources?.map(s => <p key={s.key}>{s.label} · {s.error}</p>)}
      {!stopping && terminal && state.status !== "cancelled" && action && <><p>{state.failed_sources?.length > 0 && "گزارش ناقص است."}</p>
        <ExcelExportButton autoStart={!exportDone} onComplete={() => { setExportDone(true); sessionStorage.removeItem(key); }}
          href={"/api/" + job.kind + "/export.xlsx?" + action.filters + "&matched_only=false&sort_by=announcement_at&sort_dir=desc"}
          filename={action.title + ".xlsx"} /></>}
    </dialog>
    <dialog ref={confirmation} aria-labelledby="quick-stop-title">
      <h2 id="quick-stop-title">عملیات متوقف شود؟</h2>
      <p>{action?.title}</p>
      <div className="quick-confirm-actions">
        <button className="button button--secondary" autoFocus onClick={() => confirmation.current.close()}>ادامهٔ عملیات</button>
        <button className="button button--primary" onClick={() => { confirmation.current.close(); close(true); }}>توقف عملیات</button>
      </div>
    </dialog></div>;
}
