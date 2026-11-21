import { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";

export default function GlobalSearchBar({ onNavigate, initialQuery = "" }) {
  const [value, setValue] = useState(initialQuery);
  const inputRef = useRef(null);

  useEffect(() => {
    setValue(initialQuery);
  }, [initialQuery]);

  useEffect(() => {
    function handleShortcut(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    }
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  function submit(event) {
    event.preventDefault();
    const query = value.trim();
    onNavigate(query ? "/search?q=" + encodeURIComponent(query) : "/search");
  }

  return (
    <form className="global-search-bar" role="search" onSubmit={submit}>
      <Search size={18} aria-hidden="true" />
      <input
        ref={inputRef}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="جست‌وجو در تمام مزایده‌ها و مناقصه‌ها..."
        aria-label="جست‌وجوی سراسری معاملات"
        autoComplete="off"
      />
      {value && (
        <button
          type="button"
          className="global-search-bar__clear"
          aria-label="پاک کردن عبارت جست‌وجو"
          onClick={() => { setValue(""); inputRef.current?.focus(); }}
        >
          <X size={15} />
        </button>
      )}
      <kbd dir="ltr">Ctrl K</kbd>
      <button type="submit" className="global-search-bar__submit" aria-label="جست‌وجوی سراسری">
        <Search size={17} />
      </button>
    </form>
  );
}
