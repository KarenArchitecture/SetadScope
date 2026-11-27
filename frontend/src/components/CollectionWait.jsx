import { useEffect, useState } from "react";
import { Clock, RefreshCw } from "lucide-react";
import { retryClearance } from "../services/api";
import { notifyToast } from "../utils/toast";

const format = new Intl.NumberFormat("fa-IR", { useGrouping: false });
const two = new Intl.NumberFormat("fa-IR", { minimumIntegerDigits: 2, useGrouping: false });

export default function CollectionWait({ state }) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  const [submittedId, setSubmittedId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const deadline = Number(state?.retry_at || 0);
  const manualAt = Number(state?.manual_retry_at || 0);
  const remaining = Math.max(0, Math.ceil(deadline - now));
  const retryId = state?.retry_id;
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
  const canRetry = Boolean(retryId && manualAt && now >= manualAt && now < deadline && !accepted && !submitting);
  async function retry() {
    if (!canRetry) return;
    setSubmitting(true);
    try {
      await retryClearance(retryId);
      setSubmittedId(retryId);
    } catch (error) {
      notifyToast("info", error.response?.data?.detail || "بررسی خودکار طبق برنامه ادامه دارد.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="collection-wait">
      <p>برای رعایت ظرفیت پاسخ‌گویی سامانه، دریافت سری بعدی اطلاعات به‌صورت خودکار ادامه می‌یابد.</p>
      <div className="collection-wait__controls">
        <span className="collection-wait__countdown">
          <Clock size={15} aria-hidden="true" />
          {accepted || remaining === 0 ? "در حال آماده‌سازی دریافت..." : (
            <>زمان باقی‌مانده: <strong dir="ltr" role="timer">{two.format(Math.floor(remaining / 60))}:{two.format(remaining % 60)}</strong></>
          )}
        </span>
        <button type="button" className="button button--secondary collection-wait__retry"
          onClick={retry} disabled={!canRetry}
          title={manualAt ? "بررسی دستی پس از پایان حداقل زمان انتظار" : "بررسی خودکار پس از پایان زمان انتظار انجام می‌شود"}>
          <RefreshCw size={14} aria-hidden="true" />
          {accepted ? "درخواست ثبت شد" : "تلاش مجدد"}
        </button>
      </div>
      {manualAt > now && manualAt < deadline && !accepted && (
        <small>امکان بررسی دستی پس از {format.format(Math.ceil(manualAt - now))} ثانیه فعال می‌شود.</small>
      )}
    </div>
  );
}
