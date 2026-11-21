import { useEffect, useState } from "react";
import { CheckCircle2, KeyRound, LoaderCircle, Plus, RotateCcw, Trash2 } from "lucide-react";
import Sidebar from "../components/Sidebar";
import ThemeToggle from "../components/ThemeToggle";
import { getKeywords, updateKeywords } from "../services/api";
import "./Dashboard.css";
import "./Settings.css";
import "../styles/redesign.css";

export default function Settings({ onNavigate, theme, onThemeToggle, sidebarCollapsed, onSidebarToggle }) {
  const [keywords, setKeywords] = useState([]);
  const [original, setOriginal] = useState([]);
  const [newKeyword, setNewKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const changed = JSON.stringify(keywords) !== JSON.stringify(original);

  useEffect(() => {
    let active = true;
    getKeywords().then((data) => {
      if (active) {
        setKeywords(data.keywords);
        setOriginal(data.keywords);
      }
    }).catch((err) => {
      if (active) setError(err.response?.data?.detail || "دریافت کلیدواژه‌ها ناموفق بود.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  function changeAt(index, value) {
    setKeywords((current) => current.map((word, i) => i === index ? value : word));
    setSuccess(false);
  }

  function addKeyword(event) {
    event.preventDefault();
    const value = newKeyword.trim();
    if (!value) return;
    setKeywords((current) => [...current, value]);
    setNewKeyword("");
    setError("");
    setSuccess(false);
  }

  async function saveKeywords(event) {
    event.preventDefault();
    setError("");
    setSuccess(false);
    setSaving(true);
    try {
      const result = await updateKeywords(keywords);
      setKeywords(result.keywords);
      setOriginal(result.keywords);
      setSuccess(true);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "ذخیره تنظیمات ناموفق بود.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={"app-shell " + (sidebarCollapsed ? "app-shell--collapsed" : "")}>
      <Sidebar page="settings" onNavigate={onNavigate} collapsed={sidebarCollapsed} onToggle={onSidebarToggle} />
      <main className="main-content">
        <header className="topbar">
          <div className="topbar__breadcrumb">SetadScope <span>‹</span> تنظیمات سایت</div>
          <ThemeToggle theme={theme} onToggle={onThemeToggle} />
        </header>
        <div className="dashboard-content settings-content">
          <section className="page-heading">
            <div>
              <span className="eyebrow">شخصی‌سازی سامانه</span>
              <h1>تنظیمات سایت</h1>
              <p>ظاهر سامانه و کلیدواژه‌های تشخیص مزایده‌ها و مناقصه‌های مرتبط را مدیریت کنید.</p>
            </div>
          </section>

          <section className="settings-card" aria-labelledby="appearance-heading">
            <div className="settings-card__heading">
              <h2 id="appearance-heading">ظاهر و تم</h2>
              <p>تم انتخابی در مرورگر شما ذخیره می‌شود.</p>
            </div>
            <div className="settings-theme-options" role="group" aria-label="انتخاب تم">
              <button type="button" className={"settings-theme-option " + (theme === "light" ? "settings-theme-option--selected" : "")}
                aria-pressed={theme === "light"} onClick={(event) => theme === "dark" && onThemeToggle(event)}>
                روشن {theme === "light" && <CheckCircle2 size={16} />}
              </button>
              <button type="button" className={"settings-theme-option " + (theme === "dark" ? "settings-theme-option--selected" : "")}
                aria-pressed={theme === "dark"} onClick={(event) => theme === "light" && onThemeToggle(event)}>
                تاریک {theme === "dark" && <CheckCircle2 size={16} />}
              </button>
            </div>
          </section>

          <section className="settings-card" aria-labelledby="keyword-heading">
            <div className="settings-card__heading">
              <div className="settings-card__title"><KeyRound size={20} /><h2 id="keyword-heading">کلیدواژه‌های مرتبط</h2></div>
              <p>هر آگهی مزایده یا مناقصه با داشتن حداقل یکی از کلیدواژه‌های زیر مرتبط شناخته می‌شود (منطق OR).</p>
            </div>
            {loading ? (
              <div className="settings-loading"><LoaderCircle size={18} className="spin" /> در حال دریافت تنظیمات...</div>
            ) : (
              <form onSubmit={saveKeywords}>
                <div className="settings-keyword-list">
                  {keywords.map((word, i) => (
                    <div className="settings-keyword-row" key={i}>
                      <span className="settings-keyword-number">{new Intl.NumberFormat("fa-IR").format(i + 1)}</span>
                      <input aria-label={"کلیدواژه " + (i + 1)} value={word}
                        maxLength={80} onChange={(event) => changeAt(i, event.target.value)} />
                      <button type="button" className="settings-icon-button" aria-label={"حذف " + word}
                        title="حذف کلیدواژه" onClick={() => { setKeywords((current) => current.filter((_, index) => index !== i)); setSuccess(false); }}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="settings-add-row">
                  <input value={newKeyword} maxLength={80} onChange={(event) => setNewKeyword(event.target.value)}
                    placeholder="کلیدواژه جدید را وارد کنید" aria-label="کلیدواژه جدید" />
                  <button type="button" className="button button--secondary" onClick={addKeyword} disabled={!newKeyword.trim()}>
                    <Plus size={16} /> افزودن
                  </button>
                </div>
                <p className="settings-help">تغییرات در جمع‌آوری‌های بعدی اعمال می‌شوند؛ آگهی‌های موجود در آرشیو به‌صورت خودکار دوباره دسته‌بندی نمی‌شوند.</p>
                {error && <div className="settings-alert settings-alert--error" role="alert">{error}</div>}
                {success && <div className="settings-alert settings-alert--success" role="status"><CheckCircle2 size={16} /> تنظیمات ذخیره شدند.</div>}
                <div className="settings-actions">
                  <button type="button" className="button button--secondary" disabled={!changed || saving} onClick={() => { setKeywords([...original]); setError(""); setSuccess(false); }}>
                    <RotateCcw size={15} /> لغو تغییرات
                  </button>
                  <button type="submit" className="button button--primary" disabled={!changed || saving || keywords.length === 0}>
                    {saving ? <LoaderCircle size={16} className="spin" /> : <CheckCircle2 size={16} />}
                    ذخیره کلیدواژه‌ها
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
