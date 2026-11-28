import { useMemo, useState } from "react";

const EMPTY_FILTERS = {
  collection_group: "",
  province: "",
  city: "",
  status: "active",
  state: "",
  type_name: "",
  announcement_from: "",
  announcement_to: "",
  deadline_from: "",
  deadline_to: "",
  documents_deadline_from: "",
  documents_deadline_to: "",
  price_min: "",
  price_max: "",
};

const isActive = ([key, value]) => value !== "" && !(key === "status" && value === "all");

export default function useListingFilters(onError, initiallyMatched = false) {
  const [draft, setDraft] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);
  const [isOpen, setIsOpen] = useState(false);
  const [matchedOnly, setMatchedOnly] = useState(initiallyMatched);
  const [todayOnly, setTodayOnly] = useState(false);
  const params = useMemo(() => ({
    ...applied,
    matched_only: matchedOnly,
    today_only: todayOnly,
  }), [applied, matchedOnly, todayOnly]);
  const activeCount = Object.entries(applied).filter(isActive).length + Number(matchedOnly) + Number(todayOnly);

  function apply() {
    const { price_min: min, price_max: max } = draft;
    if ((min !== "" && Number(min) < 0) || (max !== "" && Number(max) < 0)) {
      onError("مبلغ پایه نمی‌تواند منفی باشد.");
      return;
    }
    if (min !== "" && max !== "" && Number(min) > Number(max)) {
      onError("حداقل مبلغ نمی‌تواند از حداکثر مبلغ بیشتر باشد.");
      return;
    }
    const invalidDates = ["announcement", "deadline", "documents_deadline"].some((name) => {
      const from = draft[name + "_from"];
      const to = draft[name + "_to"];
      return from && to && from > to;
    });
    if (invalidDates) {
      onError("تاریخ شروع هر بازه نمی‌تواند بعد از تاریخ پایان آن باشد.");
      return;
    }
    onError("");
    setApplied(draft);
    setIsOpen(false);
  }

  function resetFields(keys) {
    const fields = Object.fromEntries(keys.map((key) => [key, EMPTY_FILTERS[key]]));
    setDraft((current) => ({ ...current, ...fields }));
    setApplied((current) => ({ ...current, ...fields }));
  }

  return {
    params,
    resetFields,
    panel: {
      filters: draft,
      isOpen,
      activeCount,
      canReset: activeCount > 0 || Object.entries(draft).some(isActive),
      matchedOnly,
      todayOnly,
      onToggle: () => setIsOpen((current) => !current),
      onMatchedOnlyChange: setMatchedOnly,
      onTodayOnlyChange: setTodayOnly,
      onChange: (key, value) => setDraft((current) => ({
        ...current,
        [key]: value,
        ...(key === "province" ? { city: "" } : {}),
      })),
      onApply: apply,
      onReset: () => {
        setDraft(EMPTY_FILTERS);
        setApplied(EMPTY_FILTERS);
        setMatchedOnly(false);
        setTodayOnly(false);
        onError("");
      },
    },
  };
}
