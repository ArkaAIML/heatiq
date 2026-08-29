export type StatusTone = "neutral" | "active" | "warning" | "unavailable";

interface StatusBadgeProps {
  children: React.ReactNode;
  tone?: StatusTone;
}

export function StatusBadge({ children, tone = "neutral" }: StatusBadgeProps) {
  return (
    <span className="status-badge" data-tone={tone}>
      <span className="status-badge__mark" aria-hidden="true" />
      {children}
    </span>
  );
}
