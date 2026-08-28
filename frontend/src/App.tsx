import { useState } from "react";

import { ControlBar } from "./components/ControlBar";
import { DataValue } from "./components/DataValue";
import { SectionPanel } from "./components/SectionPanel";
import { StatusBadge } from "./components/StatusBadge";
import { SystemHeader } from "./components/SystemHeader";

const wardLabels: Record<string, string> = {
  all: "All wards",
  "ward-12": "Ward 12",
  "ward-27": "Ward 27",
};

function AwaitingData({ children }: { children: React.ReactNode }) {
  return (
    <div className="data-state" role="status">
      <span className="data-state__icon" aria-hidden="true">!</span>
      <div>
        <strong>Awaiting data</strong>
        <p>{children}</p>
      </div>
    </div>
  );
}

function App() {
  const [ward, setWard] = useState("all");
  const selectedWard = wardLabels[ward];

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to dashboard content</a>
      <SystemHeader />

      <main id="main-content" className="dashboard-container">
        <ControlBar ward={ward} onWardChange={setWard} />

        <aside className="demo-notice" aria-label="Demonstration data notice">
          <strong>Demonstration interface</strong>
          <span>No live backend or ward dataset is connected. Missing values are intentionally shown as unavailable.</span>
        </aside>

        <div className="dashboard-grid">
          <SectionPanel
            number="01"
            title="Ward GIS Overview"
            eyebrow="Spatial operations"
            status={<StatusBadge tone="unavailable">Layer unavailable</StatusBadge>}
            className="panel-map"
          >
            <div className="map-placeholder" role="img" aria-label="GIS ward map integration placeholder">
              <div className="map-placeholder__grid" aria-hidden="true" />
              <div className="map-placeholder__message">
                <span className="map-placeholder__crosshair" aria-hidden="true">＋</span>
                <strong>Ward boundary layer not loaded</strong>
                <p>Integration surface reserved for validated GeoJSON and severity overlays.</p>
              </div>
              <div className="map-placeholder__legend" aria-label="Future severity legend">
                <span>Future severity legend</span>
                <i className="legend-swatch is-neutral" /> No data
                <i className="legend-swatch is-amber" /> Warning
                <i className="legend-swatch is-red" /> Severe
              </div>
            </div>
          </SectionPanel>

          <SectionPanel
            number="01A"
            title="Selected Ward Brief"
            eyebrow="Administrative context"
            status={<StatusBadge>{selectedWard}</StatusBadge>}
            className="panel-ward-brief"
          >
            <dl className="summary-list">
              <div><dt>Selection</dt><dd>{selectedWard} · Demo only</dd></div>
              <div><dt>Heat severity</dt><dd>Unavailable</dd></div>
              <div><dt>Observation time</dt><dd>Awaiting data</dd></div>
              <div><dt>Data freshness</dt><dd>Not connected</dd></div>
            </dl>
            <AwaitingData>Connect a validated ward context and hazard feed.</AwaitingData>
          </SectionPanel>

          <SectionPanel number="02" title="Current Weather" eyebrow="Observed conditions" className="panel-weather">
            <dl className="metric-grid">
              <DataValue label="Air temperature" unit="°C" />
              <DataValue label="Relative humidity" unit="%" />
              <DataValue label="Wind speed" unit="m/s" />
              <DataValue label="Surface pressure" unit="Pa" />
            </dl>
          </SectionPanel>

          <SectionPanel number="03" title="Thermal Stress" eyebrow="Deterministic indices" className="panel-thermal">
            <dl className="metric-grid metric-grid--three">
              <DataValue label="Heat Index" detail="No thermal feed" />
              <DataValue label="UTCI" detail="No thermal feed" />
              <DataValue label="WBGT" detail="No thermal feed" />
            </dl>
          </SectionPanel>

          <SectionPanel
            number="04"
            title="D+1 Maximum Air Temperature"
            eyebrow="ML forecast · Linear Regression v1"
            status={<StatusBadge tone="unavailable">Prediction unavailable</StatusBadge>}
            className="panel-forecast"
          >
            <div className="forecast-reading">
              <span>Forecast value</span>
              <strong>Unavailable</strong>
              <small>degC · 1-day horizon</small>
            </div>
            <dl className="model-contract">
              <div><dt>Target</dt><dd>target_temperature_max_c_d1</dd></div>
              <div><dt>Model</dt><dd>Linear Regression v1</dd></div>
              <div><dt>Feature date</dt><dd>Awaiting data</dd></div>
              <div><dt>Generated at</dt><dd>Awaiting data</dd></div>
            </dl>
          </SectionPanel>

          <SectionPanel number="05" title="Dangerous-Hours Outlook" eyebrow="Separate operational feed" className="panel-danger">
            <AwaitingData>No dangerous-hours assessment is available. This panel does not derive its status from the D+1 temperature model.</AwaitingData>
            <div className="timeline-placeholder" aria-hidden="true">
              {Array.from({ length: 8 }, (_, index) => <span key={index} />)}
            </div>
          </SectionPanel>

          <SectionPanel number="06" title="Ward Context & Resources" eyebrow="Exposure and capacity" className="panel-context">
            <dl className="summary-list summary-list--compact">
              <div><dt>Population context</dt><dd>Unavailable</dd></div>
              <div><dt>Vulnerable groups</dt><dd>Awaiting data</dd></div>
              <div><dt>Cooling facilities</dt><dd>Awaiting data</dd></div>
              <div><dt>Health facilities</dt><dd>Awaiting data</dd></div>
            </dl>
          </SectionPanel>

          <SectionPanel
            number="07"
            title="Government Action Advisory"
            eyebrow="Operational circular"
            status={<StatusBadge tone="unavailable">Not issued</StatusBadge>}
            className="panel-advisory"
          >
            <article className="advisory-sheet">
              <header>
                <span>Draft decision-support output</span>
                <strong>Reference: HEATIQ / DEMO / —</strong>
              </header>
              <h3>No recommendation available</h3>
              <p>Operational actions will appear only when a validated risk assessment and recommendation response are available.</p>
              <footer>For authorised review · Demonstration interface</footer>
            </article>
          </SectionPanel>

          <SectionPanel number="08" title="Citizen Warning Preview" eyebrow="Public communication" className="panel-citizen">
            <div className="citizen-preview">
              <span className="citizen-preview__label">Preview unavailable</span>
              <h3>No public warning generated</h3>
              <p>A citizen-facing message requires validated location, timing, severity, and action guidance.</p>
            </div>
          </SectionPanel>
        </div>
      </main>

      <footer className="system-footer">
        <span>HeatIQ · Smart India Hackathon prototype</span>
        <span>Decision support only · Not an official Government of India service</span>
      </footer>
    </div>
  );
}

export default App;
