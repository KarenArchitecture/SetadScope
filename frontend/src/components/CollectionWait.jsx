import { useEffect, useState } from "react";
import { Clock, RefreshCw } from "lucide-react";
import { retryClearance } from "../services/api";
import { notifyToast } from "../utils/toast";
import "./CollectionWait.css";

const two = new Intl.NumberFormat("fa-IR", {
  minimumIntegerDigits: 2,
  useGrouping: false,
});

export default function CollectionWait({ state }) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  const [submittedId, setSubmittedId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const deadline = Number(state?.retry_at || 0);
  const remaining = Math.max(0, Math.ceil(deadline - now));
  const retryId = state?.retry_id;
  const collectionGroup =
    state?.retry_collection_group || state?.collection_group || "executive_agencies";
  const waiting = state?.status === "collecting"
    ? state.phase === "waiting_for_access"
    : state?.status === "running" && state.current_phase === "waiting_for_access";

  useEffect(() => {
    if (!waiting) return undefined;
    setNow(Date.now() / 1000);
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [waiting, deadline]);

  if (!waiting) return null;
  const accepted = Boolean(retryId && submittedId === retryId);
  const canRetry = Boolean(
    retryId && now < deadline && !accepted && !submitting,
  );

  async function retry() {
    if (!canRetry) return;
    setSubmitting(true);
    try {
      await retryClearance(retryId, collectionGroup);
      setSubmittedId(retryId);
    } catch (error) {
      notifyToast(
        "info",
        error.response?.data?.detail || "بررسی خودکار طبق برنامه ادامه دارد.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="collection-wait">
      <p>
        دریافت اطلاعات به‌صورت خودکار ادامه می‌یابد؛ اگر خواستی می‌توانی در هر
        لحظه یک بررسی زودتر انجام بدهی.
      </p>
      <div className="collection-wait__controls">
        <span className="collection-wait__countdown">
          <Clock size={15} aria-hidden="true" />
          {accepted || remaining === 0 ? "در حال آماده‌سازی دریافت..." : (
            <>
              زمان باقی‌مانده:{" "}
              <strong dir="ltr" role="timer">
                {two.format(Math.floor(remaining / 60))}:{two.format(remaining % 60)}
              </strong>
            </>
          )}
        </span>
        <button
          type="button"
          className="button button--secondary collection-wait__retry"
          onClick={retry}
          disabled={!canRetry}
          title="یک بررسی فوری انجام می‌دهد؛ ممکن است سامانه هنوز آماده پاسخ‌گویی نباشد."
        >
          <RefreshCw size={14} aria-hidden="true" />
          {accepted
            ? "درخواست ثبت شد"
            : submitting
              ? "در حال ارسال..."
              : "تلاش مجدد"}
        </button>
      </div>
      {!retryId ? (
        <small>شناسه بررسی دستی از سرور دریافت نشده است؛ دریافت خودکار ادامه دارد.</small>
      ) : !accepted ? (
        <small>
          تلاش دستی محدود به همین نوبت انتظار است؛ اگر سامانه آماده نباشد، زمان‌بندی
          خودکار دوباره تنظیم می‌شود.
        </small>
      ) : null}
    </div>
  );
}
