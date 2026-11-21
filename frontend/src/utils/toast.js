let toastSequence = 0;

export function notifyToast(type, message, options = {}) {
  const id = options.id || "setadscope-toast-" + (++toastSequence);
  const duration = options.duration ?? (type === "loading" ? 0 : 4200);

  if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
    window.dispatchEvent(new CustomEvent("setadscope:toast", {
      detail: { id, type, message, duration },
    }));
  }

  return id;
}

export function dismissToast(id) {
  if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
    window.dispatchEvent(new CustomEvent("setadscope:toast", {
      detail: { id, action: "dismiss" },
    }));
  }
}
