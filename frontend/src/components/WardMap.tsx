import type { KeyboardEvent } from "react";

import type { WardRegion, WardSeverityState } from "../types/dashboard";

interface WardMapProps {
  regions: WardRegion[];
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
      <div className="ward-map__legend" aria-label="Demonstration ward severity legend">
        <strong>Demo severity</strong>
        {Object.entries(severityLabels).map(([severity, label]) => (
          <span key={severity}>
            <i data-severity={severity} aria-hidden="true" />
            {label}
          </span>
        ))}
      </div>
      <p className="ward-map__instruction">Select a ward by mouse, or focus a region and press Enter or Space.</p>
    </div>
  );
}
