import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, LoaderCircle, RefreshCw, X } from "lucide-react";
import {
  getGlobalCollectionStatus,
  startGlobalCollection,
} from "../services/api";
import { notifyToast } from "../utils/toast";
import CollectionWait from "./CollectionWait";
import "./GlobalCollectionControl.css";

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat("fa-IR").format(value);
}

export default function GlobalCollectionControl({ apiOnline }) {
  const [state, setState] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [failuresOpen, setFailuresOpen] = useState(false);
  const [dismissedRun, setDismissedRun] = useState(null);
  const [startedHere, setStartedHere] = useState(false);

  const isRunning = state?.status === "running";
  const runId = state?.started_at || null;
  const failedSources = Array.isArray(state?.failed_sources) ? state.failed_sources : [];
  const progress = Math.max(
    0,
    Math.min(100, Number(state?.current_progress_percent ?? state?.progress_percent ?? 0)),
  );
  const showStatus = isRunning
    || (state?.status === "completed_with_errors" && dismissedRun !== runId)
    || (
      startedHere
      && ["completed", "completed_with_errors"].includes(state?.status)
      && dismissedRun !== runId
    );

  useEffect(() => {
    let active = true;
    let requestInFlight = false;

    async function refreshStatus() {
      if (requestInFlight) return;
      requestInFlight = true;
      try {
        const next = await getGlobalCollectionStatus();
        if (active) setState(next);
      } catch {
        // Keep the last known state visible during temporary API interruptions.
      } finally {
        requestInFlight = false;
      }
    }

    refreshStatus();
    const timer = window.setInterval(refreshStatus, isRunning ? 1000 : 10000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [isRunning]);

  useEffect(() => {
    if (!confirmOpen) return undefined;
    function closeOnEscape(event) {
      if (event.key === "Escape" && !submitting) setConfirmOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [confirmOpen, submitting]);

  async function handleStart() {
    setSubmitting(true);
    const toastId = notifyToast(
      "loading",
      "در حال ثبت درخواست بروزرسانی سراسری...",
      { duration: 0 },
    );
    try {
      const next = await startGlobalCollection();
      setState(next);
      setStartedHere(true);
      setDismissedRun(null);
      setFailuresOpen(false);
      setConfirmOpen(false);
      notifyToast(
        "info",
        "بروزرسانی سراسری آغاز شد؛ می‌توانی در بخش‌های دیگر سایت جابه‌جا شوی.",
        { id: toastId, duration: 4500 },
      );
    } catch (error) {
      const message = error.response?.data?.detail
        || "شروع بروزرسانی سراسری ناموفق بود.";
      notifyToast("error", message, { id: toastId, duration: 6500 });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="global-collection-control">
        <button
          type="button"
          className="global-collection-control__button"
          onClick={() => setConfirmOpen(true)}
          disabled={!apiOnline || isRunning || submitting}
          title={
            !apiOnline
              ? "ارتباط با سرور برقرار نیست"
              : isRunning
                ? "بروزرسانی سراسری در حال اجراست"
                : "بروزرسانی تمام منابع آگهی‌ها"
          }
          aria-label="بروزرسانی سراسری تمام آگهی‌ها"
        >
          {isRunning || submitting
            ? <LoaderCircle size={17} className="spin" />
            : <RefreshCw size={17} />}
          <span>
            {isRunning
              ? "در حال بروزرسانی " + formatNumber(state.current_source_index) + "/" + formatNumber(state.total_sources)
              : "بروزرسانی سراسری"}
          </span>
        </button>

        {showStatus && (
          <section
            className={
              "global-collection-control__status"
              + (state.status === "completed_with_errors" ? " global-collection-control__status--warning" : "")
            }
            aria-live="polite"
            aria-label="وضعیت بروزرسانی سراسری"
          >
            <div className="global-collection-control__status-heading">
              <div>
                <span className="global-collection-control__eyebrow">
                  {isRunning
                    ? "منبع " + formatNumber(state.current_source_index) + " از " + formatNumber(state.total_sources)
                    : "فرآیند بروزرسانی سراسری"}
                </span>
                <strong>
                  {isRunning
                    ? state.current_source_label || "در حال آماده‌سازی منبع..."
                    : state.status === "completed_with_errors"
                      ? "بروزرسانی تمام شد؛ بعضی منابع ناموفق بودند"
                      : "تمام منابع با موفقیت بروزرسانی شدند"}
                </strong>
              </div>
              <span className="global-collection-control__percent">{formatNumber(progress)}٪</span>
            </div>

            <div
              className="global-collection-control__track"
              role="progressbar"
              aria-label="پیشرفت منبع جاری"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
            >
              <div
                className={
                  "global-collection-control__fill"
                  + (isRunning ? " global-collection-control__fill--active" : "")
                }
                style={{ width: (isRunning && progress === 0 ? 2 : progress) + "%" }}
              />
            </div>

            <p className="global-collection-control__message">
              {isRunning ? state.current_message || state.message : state.message}
            </p>
            <CollectionWait state={state} />

            <div className="global-collection-control__status-footer">
              <span>
                {formatNumber(state.completed_sources || 0)} از {formatNumber(state.total_sources)} منبع انجام شده
                {" · "}
                {formatNumber(state.successful_sources || 0)} موفق
              </span>
              <div>
                {failedSources.length > 0 && (
                  <button
                    type="button"
                    className="global-collection-control__text-button"
                    onClick={() => setFailuresOpen((current) => !current)}
                    aria-expanded={failuresOpen}
                  >
                    {failuresOpen ? "بستن ناموفق‌ها" : "مشاهده ناموفق‌ها"}
                    {" (" + formatNumber(failedSources.length) + ")"}
                  </button>
                )}
                {!isRunning && (
                  <button
                    type="button"
                    className="global-collection-control__icon-button"
                    onClick={() => {
                      setDismissedRun(runId);
                      setFailuresOpen(false);
                    }}
                    aria-label="بستن وضعیت بروزرسانی"
                    title="بستن"
                  >
                    <X size={15} />
                  </button>
                )}
              </div>
            </div>

            {failuresOpen && failedSources.length > 0 && (
              <div className="global-collection-control__failures">
                <strong><AlertCircle size={15} /> منابع ناموفق</strong>
                <ul>
                  {failedSources.map((failure) => (
                    <li key={failure.key}>
                      <span>{failure.label}</span>
                      <pre>{failure.error}</pre>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {!isRunning && state.status === "completed" && (
              <div className="global-collection-control__success">
                <CheckCircle2 size={15} />
                {formatNumber(state.successful_sources)} منبع با موفقیت به‌روزرسانی شد.
              </div>
            )}
          </section>
        )}
      </div>

      {confirmOpen && (
        <div
          className="global-collection-dialog-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !submitting) setConfirmOpen(false);
          }}
        >
          <section
            className="global-collection-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="global-collection-dialog-title"
            aria-describedby="global-collection-dialog-description"
          >
            <div className="global-collection-dialog__heading">
              <span><RefreshCw size={19} /></span>
              <button
                type="button"
                className="global-collection-control__icon-button"
                onClick={() => !submitting && setConfirmOpen(false)}
                aria-label="بستن پنجره تایید"
                disabled={submitting}
              >
                <X size={17} />
              </button>
            </div>
            <h2 id="global-collection-dialog-title">بروزرسانی سراسری آگهی‌ها؟</h2>
            <p id="global-collection-dialog-description">
              با تایید این عملیات، تمام {formatNumber(state?.total_sources || 11)} منبع داده به ترتیب اجرا می‌شوند:
              پنج دسته مزایده دستگاه‌های اجرایی، پنج دسته مزایده اموال تملیکی و مناقصه‌ها.
              حراج هر مجموعه نیز به‌صورت مستقل جمع‌آوری می‌شود.
            </p>
            <p>
              این فرآیند با توجه به تعداد صفحات ممکن است زمان‌بر باشد. اگر یک Collector با خطا مواجه شود،
              فقط همان منبع ناموفق ثبت می‌شود و اجرای منابع بعدی ادامه پیدا می‌کند.
              در تمام این مدت می‌توانی در بخش‌های دیگر سایت جابه‌جا شوی؛ عملیات در سمت سرور ادامه خواهد داشت.
            </p>
            <div className="global-collection-dialog__actions">
              <button
                type="button"
                className="global-collection-dialog__cancel"
                onClick={() => setConfirmOpen(false)}
                disabled={submitting}
              >
                انصراف
              </button>
              <button
                type="button"
                className="global-collection-dialog__confirm"
                onClick={handleStart}
                disabled={submitting || !apiOnline}
              >
                {submitting
                  ? <LoaderCircle size={16} className="spin" />
                  : <RefreshCw size={16} />}
                شروع بروزرسانی
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
