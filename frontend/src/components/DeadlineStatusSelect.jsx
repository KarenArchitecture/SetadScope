export default function DeadlineStatusSelect({ value = "all", onChange, disabled = false }) {
  return (
    <select
      value={value || "all"}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="all">همه وضعیت‌ها</option>
      <option value="active">دارای مهلت</option>
      <option value="archive">مهلت تمام‌شده</option>
    </select>
  );
}
