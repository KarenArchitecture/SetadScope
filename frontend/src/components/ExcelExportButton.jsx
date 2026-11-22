import { useEffect, useRef, useState } from "react";
import { CheckCircle2, FileSpreadsheet, LoaderCircle } from "lucide-react";
import { notifyToast } from "../utils/toast";
import "./ExcelExportButton.css";

function formatNumber(value) {
  return new Intl.NumberFormat("fa-IR").format(value);
}

export default function ExcelExportButton({
  href,
  filename = "setadscope_export.xlsx",
  label = "خروجی Excel",
}) {
  const [progress, setProgress] = useState({ status: "idle", percent: null, error: "" });
  const requestRef = useRef(null);
  const isBusy = progress.status === "preparing" || progress.status === "downloading";

  useEffect(() => () => requestRef.current?.abort(), []);

  function handleExport() {
    if (isBusy || !href) return;

    const request = new XMLHttpRequest();
    requestRef.current = request;
    setProgress({ status: "preparing", percent: null, error: "" });

    const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
    const requestUrl = /^https?:\/\//i.test(href) ? href : apiBaseUrl + href;
    request.open("GET", requestUrl, true);
    request.responseType = "blob";
    request.setRequestHeader(
      "Accept",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    );

    request.onreadystatechange = () => {
      if (request.readyState === XMLHttpRequest.HEADERS_RECEIVED && request.status >= 200 && request.status < 300) {
        setProgress((current) => (
          current.status === "preparing"
            ? { ...current, status: "downloading" }
            : current
        ));
      }
    };

    request.onprogress = (event) => {
      const percent = event.lengthComputable && event.total > 0
        ? Math.min(100, Math.round((event.loaded / event.total) * 100))
        : null;
      setProgress({ status: "downloading", percent, error: "" });
    };

    request.onload = async () => {
      requestRef.current = null;

      if (request.status >= 200 && request.status < 300) {
        const blob = request.response;
        if (!blob || blob.size === 0) {
          const message = "فایل خروجی خالی است؛ آماده‌سازی خروجی ناموفق بود.";
          setProgress({ status: "error", percent: null, error: message });
          notifyToast("error", message, { duration: 5000 });
          return;
        }

        const objectUrl = window.URL.createObjectURL(blob);
        const downloadLink = document.createElement("a");
        downloadLink.href = objectUrl;
        downloadLink.download = filename;
        document.body.appendChild(downloadLink);
        downloadLink.click();
        downloadLink.remove();
        window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 1000);

        setProgress({ status: "complete", percent: 100, error: "" });
        notifyToast("success", "فایل Excel آماده و دانلود شد.", { duration: 3500 });
        window.setTimeout(() => {
          setProgress((current) => (
            current.status === "complete"
              ? { status: "idle", percent: null, error: "" }
              : current
          ));
        }, 1800);
        return;
      }

      let message = "آماده‌سازی خروجی Excel ناموفق بود.";
      try {
        const payload = await request.response.text();
        const parsed = JSON.parse(payload);
        if (parsed.detail) message = parsed.detail;
      } catch {
        // Keep the safe, user-facing fallback message.
      }
      setProgress({ status: "error", percent: null, error: message });
      notifyToast("error", message, { duration: 5500 });
    };

    request.onerror = () => {
      requestRef.current = null;
      const message = "ارتباط با سرور هنگام تهیه خروجی Excel قطع شد.";
      setProgress({ status: "error", percent: null, error: message });
      notifyToast("error", message, { duration: 5500 });
    };

    request.onabort = () => {
      requestRef.current = null;
      setProgress({ status: "idle", percent: null, error: "" });
    };

    request.send();
  }

  return (
    <div className="excel-export">
      <button
        type="button"
        className="button button--secondary excel-export__button"
        onClick={handleExport}
        disabled={isBusy}
        aria-label={
          progress.status === "preparing"
            ? "در حال آماده‌سازی خروجی Excel"
            : progress.status === "downloading"
              ? "در حال دانلود خروجی Excel"
              : label
        }
      >
        {isBusy
          ? <LoaderCircle size={16} className="spin" />
          : progress.status === "complete"
            ? <CheckCircle2 size={16} />
            : <FileSpreadsheet size={16} />}
        <span>
          {progress.status === "preparing"
            ? "در حال آماده‌سازی..."
            : progress.status === "downloading"
              ? "در حال دانلود..."
              : progress.status === "error"
                ? "تلاش مجدد"
                : label}
        </span>
      </button>

      {isBusy && (
        <div className="excel-export__progress" role="status" aria-live="polite">
          <div className="excel-export__progress-copy">
            <span>
              {progress.status === "preparing"
                ? "در حال آماده‌سازی فایل..."
                : progress.percent === null
                  ? "در حال دریافت فایل..."
                  : "در حال دانلود فایل..."}
            </span>
            {progress.percent !== null && (
              <strong>{formatNumber(progress.percent)}٪</strong>
            )}
          </div>
          <div
            className="excel-export__track"
            role="progressbar"
            aria-label="پیشرفت آماده‌سازی و دریافت خروجی Excel"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress.percent === null ? undefined : progress.percent}
          >
            <span
              className={
                "excel-export__fill" +
                (progress.percent === null ? " excel-export__fill--indeterminate" : "")
              }
              style={progress.percent === null ? undefined : { width: progress.percent + "%" }}
            />
          </div>
        </div>
      )}

      {progress.status === "error" && (
        <span className="excel-export__error">{progress.error}</span>
      )}
    </div>
  );
}
