import { useState, type KeyboardEvent } from "react";

import type { WardRegion, WardSeverityState } from "../types/dashboard";

interface WardMapProps {
  regions: readonly WardRegion[];
  onSelectWard: (wardId: string) => void;
}

const severityLabels: Record<WardSeverityState, string> = {
  "no-data": "No data",
  low: "Low",
  moderate: "Moderate",
  high: "High",
  "very-high": "Very high",
  severe: "Severe",
  critical: "Critical",
  extreme: "Extreme",
};

type MapLayer = "severity" | "heat-intensity";

const intensityLabels = ["Lower", "Moderate", "Elevated", "High"] as const;

export function WardMap({ regions, onSelectWard }: WardMapProps) {
  const [layer, setLayer] = useState<MapLayer>("severity");

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
      <div className="ward-map__toolbar">
        <span>Map layer</span>
        <div className="ward-map__layer-control" role="group" aria-label="Map layer">
          <button
            type="button"
            aria-pressed={layer === "severity"}
            onClick={() => setLayer("severity")}
          >
            Ward Severity
          </button>
          <button
            type="button"
            aria-pressed={layer === "heat-intensity"}
            onClick={() => setLayer("heat-intensity")}
          >
            Heat Intensity
          </button>
        </div>
      </div>
      <div className="ward-map__notice" id="ward-map-description">
        {layer === "severity" ? (
          <>
            <strong>Demonstration ward layout</strong>
            <span>Not authoritative GIS boundaries · Severity is mock presentation data and is not derived from the D+1 model.</span>
          </>
        ) : (
          <>
            <strong>DEMONSTRATION HEAT INTENSITY</strong>
            <span>Illustrative visualization · Not model output · Not authoritative GIS data</span>
          </>
        )}
      </div>
      {regions.length === 0 ? (
        <div className="ward-map__empty" role="status">
          <strong>Ward geometry unavailable</strong>
          <span>No demonstration ward regions were supplied by the repository.</span>
        </div>
      ) : (
        <svg
          className="ward-map__canvas"
          data-layer={layer}
          viewBox="0 0 640 360"
          role="group"
          aria-label="Selectable demonstration ward layout"
          aria-describedby="ward-map-description"
        >
          <defs>
            <clipPath id="demonstration-map-region">
              {regions.map((region) => <polygon key={region.wardId} points={region.points} />)}
            </clipPath>
            <radialGradient id="heat-zone-lower">
              <stop offset="0" stopColor="#7da88c" stopOpacity="0.72" />
              <stop offset="1" stopColor="#7da88c" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="heat-zone-moderate">
              <stop offset="0" stopColor="#d5ae4f" stopOpacity="0.78" />
              <stop offset="1" stopColor="#d5ae4f" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="heat-zone-elevated">
              <stop offset="0" stopColor="#c9702b" stopOpacity="0.8" />
              <stop offset="1" stopColor="#c9702b" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="heat-zone-high">
              <stop offset="0" stopColor="#a4443c" stopOpacity="0.82" />
              <stop offset="1" stopColor="#a4443c" stopOpacity="0" />
            </radialGradient>
          </defs>
          <rect className="ward-map__ground" x="0" y="0" width="640" height="360" />
          {layer === "heat-intensity" ? (
            <g
              className="ward-map__heat-overlay"
              clipPath="url(#demonstration-map-region)"
              aria-hidden="true"
            >
              <rect x="0" y="0" width="640" height="360" fill="#dbe4d8" />
              <ellipse cx="125" cy="245" rx="210" ry="175" fill="url(#heat-zone-lower)" />
              <ellipse cx="250" cy="105" rx="205" ry="145" fill="url(#heat-zone-moderate)" />
              <ellipse cx="410" cy="225" rx="225" ry="170" fill="url(#heat-zone-elevated)" />
              <ellipse cx="525" cy="105" rx="145" ry="120" fill="url(#heat-zone-high)" />
            </g>
          ) : null}
          {regions.map((region) => (
            <g
              key={region.wardId}
              className="ward-region"
              data-severity={region.severity}
              data-selected={region.selected ? "true" : "false"}
              role="button"
              tabIndex={0}
              aria-pressed={region.selected}
              aria-label={layer === "severity"
                ? `${region.wardName}, ${severityLabels[region.severity]} demonstration severity`
                : `${region.wardName}, selectable region, demonstration heat intensity layer`}
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
      {layer === "severity" ? (
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
      ) : (
        <div className="ward-map__legend" role="group" aria-labelledby="heat-intensity-legend">
          <strong id="heat-intensity-legend">Demo intensity</strong>
          <ul>
            {intensityLabels.map((label) => (
              <li key={label}>
                <i data-intensity={label.toLowerCase()} aria-hidden="true" />
                {label}
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="ward-map__instruction">Select a ward by mouse, or focus a region and press Enter or Space.</p>
    </div>
  );
}
