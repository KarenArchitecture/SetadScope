import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Info,
  LoaderCircle,
  X,
} from "lucide-react";
import "./ToastViewport.css";

const TOAST_ICONS = {
  loading: LoaderCircle,
  success: CheckCircle2,
  error: AlertCircle,
  info: Info,
};

export default function ToastViewport() {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  useEffect(() => {
    function removeToast(id) {
      const timer = timers.current.get(id);
      if (timer) window.clearTimeout(timer);
      timers.current.delete(id);
      setToasts((current) => current.filter((item) => item.id !== id));
    }

    function handleToast(event) {
      const detail = event.detail || {};
      if (!detail.id) return;
      if (detail.action === "dismiss") {
        removeToast(detail.id);
        return;
      }

      const item = {
        id: detail.id,
        type: TOAST_ICONS[detail.type] ? detail.type : "info",
        message: String(detail.message || ""),
        duration: Number(detail.duration ?? 4200),
      };

      setToasts((current) => {
        const exists = current.some((toast) => toast.id === item.id);
        if (exists) return current.map((toast) => toast.id === item.id ? item : toast);
        return [...current, item].slice(-4);
      });

      const previousTimer = timers.current.get(item.id);
      if (previousTimer) window.clearTimeout(previousTimer);
      timers.current.delete(item.id);

      if (item.duration > 0) {
        const timer = window.setTimeout(() => removeToast(item.id), item.duration);
        timers.current.set(item.id, timer);
      }
    }

    window.addEventListener("setadscope:toast", handleToast);
    return () => {
      window.removeEventListener("setadscope:toast", handleToast);
      timers.current.forEach((timer) => window.clearTimeout(timer));
      timers.current.clear();
    };
  }, []);

  function dismiss(id) {
    const timer = timers.current.get(id);
    if (timer) window.clearTimeout(timer);
    timers.current.delete(id);
    setToasts((current) => current.filter((item) => item.id !== id));
  }

  return (
    <div className="toast-viewport" aria-live="polite" aria-relevant="additions text">
      {toasts.map((item) => {
        const Icon = TOAST_ICONS[item.type];
        return (
          <article
            className={"app-toast app-toast--" + item.type}
            key={item.id}
            role={item.type === "error" ? "alert" : "status"}
            dir="rtl"
          >
            <span className="app-toast__icon" aria-hidden="true">
              <Icon size={19} className={item.type === "loading" ? "spin" : ""} />
            </span>
            <p className="app-toast__message">{item.message}</p>
            <button
              type="button"
              className="app-toast__close"
              aria-label="بستن اعلان"
              onClick={() => dismiss(item.id)}
            >
              <X size={15} />
            </button>
          </article>
        );
      })}
    </div>
  );
}
