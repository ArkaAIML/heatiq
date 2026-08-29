import type { DashboardSnapshot, PresentedValue } from "../../types/dashboard";
import { DataStateNotice } from "../DataStateNotice";
import { SectionPanel } from "../SectionPanel";
import { StatusBadge } from "../StatusBadge";

interface ResponsePanelsProps {
  snapshot: DashboardSnapshot;
}

function displayValue<T>(value: PresentedValue<T>, format: (present: T) => string): string {
  return value.value === null ? "Unavailable" : format(value.value);
}

export function ResponsePanels({ snapshot }: ResponsePanelsProps) {
  const { dangerousHours, wardContext, advisory, citizenWarning } = snapshot;
  const dangerousHoursAvailable = dangerousHours.startTime !== null && dangerousHours.endTime !== null;
  const isLive = snapshot.dataMode === "live";

  return (
    <>
      <SectionPanel
        number="05"
        title="Dangerous-Hours Outlook"
        eyebrow="Separate operational feed"
        status={<StatusBadge tone="warning">{dangerousHoursAvailable ? "Demo window" : "Unavailable"}</StatusBadge>}
        className="panel-danger"
      >
        {dangerousHoursAvailable ? (
          <div className="danger-window">
            <div>
              <span>Demonstration time window</span>
              <strong>{dangerousHours.startTime}–{dangerousHours.endTime}</strong>
            </div>
            <div>
              <span>Operational severity</span>
              <strong>{dangerousHours.severity?.replace("-", " ")}</strong>
            </div>
          </div>
        ) : (
          <DataStateNotice state="unavailable" title="Dangerous hours unavailable">
            No dangerous-hours assessment was supplied.
          </DataStateNotice>
        )}
        <p className="panel-note"><strong>{dangerousHours.sourceLabel}.</strong> {dangerousHours.note}</p>
        {dangerousHoursAvailable ? (
          <div className="timeline-placeholder" aria-label="Demonstration dangerous-hours timeline">
            {Array.from({ length: 8 }, (_, index) => (
              <span key={index} className={index >= 2 && index <= 5 ? "is-warning" : ""} />
            ))}
          </div>
        ) : null}
      </SectionPanel>

      <SectionPanel
        number="06"
        title="Ward Context & Resources"
        eyebrow={`Exposure and capacity · ${isLive ? "Backend API" : "Demo repository"}`}
        status={<StatusBadge>{isLive ? "Backend data" : "Demo data"}</StatusBadge>}
        className="panel-context"
      >
        <dl className="summary-list summary-list--compact">
          <div><dt>Population context</dt><dd>{displayValue(wardContext.population, (value) => `${value.toLocaleString("en-IN")} people`)}</dd></div>
          <div><dt>Cooling facilities</dt><dd>{displayValue(wardContext.coolingFacilities, (value) => `${value} listed`)}</dd></div>
          <div><dt>Health facilities</dt><dd>{displayValue(wardContext.healthFacilities, (value) => `${value} listed`)}</dd></div>
          <div><dt>Verified water points</dt><dd>{displayValue(wardContext.waterPoints, (value) => `${value} listed`)}</dd></div>
        </dl>
        {wardContext.vulnerableGroups.value ? (
          <div className="context-groups">
            <span>{isLive ? "Vulnerable-group context" : "Demonstration vulnerable-group context"}</span>
            <ul>{wardContext.vulnerableGroups.value.map((group) => <li key={group}>{group}</li>)}</ul>
          </div>
        ) : null}
      </SectionPanel>

      <SectionPanel
        number="07"
        title="Government Action Advisory"
        eyebrow={`Operational circular · ${isLive ? "Backend rules" : "Demonstration"}`}
        status={<StatusBadge tone="warning">{isLive ? "Backend advisory" : "Demo advisory"}</StatusBadge>}
        className="panel-advisory"
      >
        <article className="advisory-sheet">
          <header>
            <span>{isLive ? "Backend decision-support output" : "Demonstration decision-support output"}</span>
            <strong>Reference: {advisory.reference ?? "Unavailable"}</strong>
          </header>
          <h3>{advisory.title}</h3>
          {advisory.actions.length > 0 ? (
            <ol>{advisory.actions.map((action) => <li key={action}>{action}</li>)}</ol>
          ) : (
            <p>No operational recommendation is available.</p>
          )}
          <div className="reason-codes">Reason codes: {advisory.reasonCodes.join(" · ") || "Unavailable"}</div>
          <footer>For authorised review · {isLive ? "Backend-connected interface" : "Demonstration interface"}</footer>
        </article>
      </SectionPanel>

      <SectionPanel
        number="08"
        title="Citizen Warning Preview"
        eyebrow={`Public communication · ${isLive ? "Unavailable" : "Demonstration"}`}
        className="panel-citizen"
      >
        <div className="citizen-preview">
          <span className="citizen-preview__label">{isLive ? "Unavailable · Not issued" : "Demonstration message · Not issued"}</span>
          <h3>{citizenWarning.headline}</h3>
          <p>{citizenWarning.message}</p>
          <dl>
            <div><dt>Valid from</dt><dd>{citizenWarning.validFrom ?? "Unavailable"}</dd></div>
            <div><dt>Valid until</dt><dd>{citizenWarning.validUntil ?? "Unavailable"}</dd></div>
          </dl>
        </div>
      </SectionPanel>
    </>
  );
}
