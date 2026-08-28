import { StatusBadge } from "./StatusBadge";

export function SystemHeader() {
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
            <dd>Bhubaneswar · Demonstration</dd>
          </div>
          <div>
            <dt>Last updated</dt>
            <dd>Awaiting live data</dd>
          </div>
          <div>
            <dt>System status</dt>
            <dd><StatusBadge tone="unavailable">Demo mode</StatusBadge></dd>
          </div>
        </dl>
      </div>
    </header>
  );
}
