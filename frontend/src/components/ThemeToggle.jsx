import { Moon, Sun } from "lucide-react";

export default function ThemeToggle({ theme, onToggle }) {
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={onToggle}
      aria-label={theme === "dark" ? "فعال‌کردن تم روشن" : "فعال‌کردن تم تاریک"}
      title={theme === "dark" ? "تم روشن" : "تم تاریک"}
    >
      {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
      <span>{theme === "dark" ? "روشن" : "تاریک"}</span>
    </button>
  );
}
