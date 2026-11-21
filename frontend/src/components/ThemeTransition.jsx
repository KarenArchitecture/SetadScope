import "./ThemeTransition.css";

/**
 * The destination theme covers the current UI before its tokens change,
 * then withdraws from the same click position to reveal a fully repainted page.
 */
export default function ThemeTransition({ transition, onAnimationEnd }) {
  const { x, y, radius, to, phase } = transition;
  return (
    <div
      className={"theme-transition theme-transition--" + to + " theme-transition--" + phase}
      style={{
        "--theme-x": x + "px",
        "--theme-y": y + "px",
        "--theme-radius": radius + "px",
      }}
      onAnimationEnd={(event) => {
        if (event.target === event.currentTarget) onAnimationEnd();
      }}
    >
      <div className="theme-transition__status" role="status" aria-live="polite">
        <span className="theme-transition__mark" aria-hidden="true" />
        <strong>در حال تغییر ظاهر سایت</strong>
        <span>در حال هماهنگ‌سازی رنگ‌ها…</span>
        <span className="theme-transition__progress" aria-hidden="true">
          <span className="theme-transition__progress-fill" />
        </span>
      </div>
    </div>
  );
}
