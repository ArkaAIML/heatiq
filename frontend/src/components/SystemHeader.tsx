import { StatusBadge } from "./StatusBadge";

interface SystemHeaderProps {
  operationalArea: string;
  updatedLabel: string;
  state: "loading" | "demonstration" | "stale" | "error";
}

export function SystemHeader({ operationalArea, updatedLabel, state }: SystemHeaderProps) {
  const statusLabel = {
    loading: "Loading",
    demonstration: "Demo mode",
    stale: "Stale demo",
    error: "Data error",
  }[state];
  const tone = state === "error" || state === "stale" ? "warning" : "unavailable";

  return (
    <header className="system-header">
      <div className="identity-rule" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="system-header__utility">
        <span>Smart India Hackathon Prototype</span>
        <span>Decision-support interface · Not an official government service</span>
      </div>
      <div className="system-header__main">
        <div className="system-identity">
          <div className="system-identity__monogram" aria-hidden="true">HQ</div>
          <div>
            <p className="system-identity__kicker">Extreme heat monitoring cell</p>
            <h1>HeatIQ</h1>
            <p>Extreme Heat Decision Support System</p>
          </div>
        </div>
        <dl className="system-metadata">
          <div>
            <dt>Operational area</dt>
            <dd>{operationalArea}</dd>
          </div>
          <div>
            <dt>Last updated</dt>
            <dd>{updatedLabel}</dd>
          </div>
          <div>
            <dt>System status</dt>
            <dd><StatusBadge tone={tone}>{statusLabel}</StatusBadge></dd>
          </div>
        </dl>
      </div>
    </header>
  );
}
