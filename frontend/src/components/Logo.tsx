/**
 * NIK logo mark plus a real-text wordmark. The wordmark is HTML text, so the
 * site name stays readable if the SVG fails or styles are disabled. The mark
 * matches `public/favicon.svg`; keep both in sync when changing it.
 */
export function Logo() {
  return (
    <span className="logo">
      <svg className="logo__mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <rect width="32" height="32" rx="7" fill="var(--color-brand)" />
        <path
          d="M6 24V8l7.5 16V8M18 8v16M22 8v16M28 8l-6 8 6 8"
          fill="none"
          stroke="var(--color-brand-contrast)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="logo__wordmark">Nailed It Kitchen</span>
    </span>
  );
}
