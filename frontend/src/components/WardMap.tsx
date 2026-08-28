import type { KeyboardEvent } from "react";

import type { WardRegion, WardSeverityState } from "../types/dashboard";

interface WardMapProps {
  regions: readonly WardRegion[];
  onSelectWard: (wardId: string) => void;
}

const severityLabels: Record<WardSeverityState, string> = {
  "no-data": "No data",
  moderate: "Moderate",
  high: "High",
  "very-high": "Very high",
  severe: "Severe",
};

export function WardMap({ regions, onSelectWard }: WardMapProps) {
  const activateWithKeyboard = (
    event: KeyboardEvent<SVGGElement>,
    wardId: string,
  ) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelectWard(wardId);
    }
  };

  return (
    <div className="ward-map">
      <div className="ward-map__notice" id="ward-map-description">
        <strong>Demonstration ward layout</strong>
        <span>Not authoritative GIS boundaries · Severity is mock presentation data and is not derived from the D+1 model.</span>
      </div>
      {regions.length === 0 ? (
        <div className="ward-map__empty" role="status">
          <strong>Ward geometry unavailable</strong>
          <span>No demonstration ward regions were supplied by the repository.</span>
        </div>
      ) : (
        <svg
          className="ward-map__canvas"
          viewBox="0 0 640 360"
          role="group"
          aria-label="Selectable demonstration ward layout"
          aria-describedby="ward-map-description"
        >
          <rect className="ward-map__ground" x="0" y="0" width="640" height="360" />
          {regions.map((region) => (
            <g
              key={region.wardId}
              className="ward-region"
              data-severity={region.severity}
              data-selected={region.selected ? "true" : "false"}
              role="button"
              tabIndex={0}
              aria-pressed={region.selected}
              aria-label={`${region.wardName}, ${severityLabels[region.severity]} demonstration severity`}
              onClick={() => onSelectWard(region.wardId)}
              onKeyDown={(event) => activateWithKeyboard(event, region.wardId)}
            >
              <polygon points={region.points} />
              <text x={region.labelX} y={region.labelY} textAnchor="middle">
                {region.wardName.replace("Ward ", "W-")}
              </text>
              <title>{region.wardName} · {severityLabels[region.severity]} · Demonstration geometry</title>
            </g>
          ))}
        </svg>
      )}
      <div className="ward-map__legend" role="group" aria-labelledby="ward-severity-legend">
        <strong id="ward-severity-legend">Demo severity</strong>
        <ul>
          {Object.entries(severityLabels).map(([severity, label]) => (
            <li key={severity}>
              <i data-severity={severity} aria-hidden="true" />
              {label}
            </li>
          ))}
        </ul>
      </div>
      <p className="ward-map__instruction">Select a ward by mouse, or focus a region and press Enter or Space.</p>
    </div>
  );
}
