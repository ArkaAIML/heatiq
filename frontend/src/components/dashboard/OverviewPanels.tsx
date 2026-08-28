import type { DashboardSnapshot } from "../../types/dashboard";
import { DataStateNotice } from "../DataStateNotice";
import { SectionPanel } from "../SectionPanel";
import { StatusBadge } from "../StatusBadge";

interface OverviewPanelsProps {
  snapshot: DashboardSnapshot;
}

export function OverviewPanels({ snapshot }: OverviewPanelsProps) {
  const { location, wardContext } = snapshot;

  return (
    <>
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
        status={<StatusBadge>{location.wardName}</StatusBadge>}
        className="panel-ward-brief"
      >
        <dl className="summary-list">
          <div><dt>Selection</dt><dd>{location.wardName} · Demo data</dd></div>
          <div><dt>Heat severity</dt><dd>{wardContext.heatSeverity.value ?? "Unavailable"}</dd></div>
          <div><dt>Observation area</dt><dd>{location.city}, {location.district}</dd></div>
          <div><dt>Data freshness</dt><dd>{snapshot.freshness === "stale" ? "Stale" : "Demo snapshot"}</dd></div>
        </dl>
        <DataStateNotice
          state={snapshot.freshness === "stale" ? "stale" : "demonstration"}
          title={snapshot.freshness === "stale" ? "Stale demonstration data" : "Demonstration data"}
        >
          Values are illustrative and are not connected to a live ward feed.
        </DataStateNotice>
      </SectionPanel>
    </>
  );
}
