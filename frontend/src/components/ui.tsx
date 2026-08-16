import React from "react";

/* ---------- Layout ---------- */

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
      <div>
        <h2 className="text-xl font-semibold text-content">{title}</h2>
        {subtitle && (
          <p className="mt-1 text-sm text-content-muted max-w-2xl">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({
  title,
  description,
  actions,
  children,
  className = "",
}: {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 px-5 py-4 border-b border-edge">
          <div>
            {title && (
              <h3 className="text-sm font-semibold text-content">{title}</h3>
            )}
            {description && (
              <p className="mt-0.5 text-xs text-content-muted">{description}</p>
            )}
          </div>
          {actions}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

/* ---------- Data display ---------- */

export function StatCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "default" | "ok" | "warn" | "danger" | "brand";
}) {
  const toneClass = {
    default: "text-content",
    ok: "text-ok",
    warn: "text-warn",
    danger: "text-danger",
    brand: "text-brand",
  }[tone];

  return (
    <div className="card px-4 py-3">
      <p className="label">{label}</p>
      <p className={`mt-1 text-2xl font-bold tabular-nums ${toneClass}`}>
        {value}
      </p>
      {hint && <p className="mt-0.5 text-xs text-content-subtle">{hint}</p>}
    </div>
  );
}

const BADGE_TONES: Record<string, string> = {
  ok: "bg-ok/10 text-ok border-ok/30",
  warn: "bg-warn/10 text-warn border-warn/30",
  danger: "bg-danger/10 text-danger border-danger/30",
  brand: "bg-brand/10 text-brand border-brand/30",
  accent: "bg-accent/10 text-accent border-accent/30",
  neutral: "bg-content-subtle/10 text-content-muted border-content-subtle/30",
};

export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: keyof typeof BADGE_TONES | string;
}) {
  return (
    <span className={`badge ${BADGE_TONES[tone] || BADGE_TONES.neutral}`}>
      {children}
    </span>
  );
}

/* ---------- States ---------- */

export function EmptyState({
  icon = "○",
  title,
  description,
  action,
}: {
  icon?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-14 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-surface-overlay text-lg text-content-subtle">
        {icon}
      </div>
      <p className="text-sm font-medium text-content">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-content-muted">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBanner({
  error,
  onDismiss,
}: {
  error: string;
  onDismiss?: () => void;
}) {
  return (
    <div className="mb-4 flex items-start gap-3 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 animate-fade-up">
      <span className="mt-0.5 text-danger">!</span>
      <p className="flex-1 whitespace-pre-wrap text-sm text-danger">{error}</p>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-danger/60 transition-colors hover:text-danger"
          aria-label="Dismiss error"
        >
          ✕
        </button>
      )}
    </div>
  );
}

export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`h-4 w-4 animate-spin ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.4 0 0 5.4 0 12h4z"
      />
    </svg>
  );
}

/* ---------- Helpers ---------- */

export function ScoreBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score * 100));
  // Similarity below ~0.4 is usually noise; colour-code so weak retrieval
  // is visible at a glance rather than hidden behind a number.
  const tone = pct >= 70 ? "bg-ok" : pct >= 45 ? "bg-warn" : "bg-danger";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-edge-strong">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs tabular-nums text-content-muted">
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

export function formatNumber(n: number | undefined | null): string {
  return (n ?? 0).toLocaleString();
}
