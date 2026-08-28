import type { DashboardSnapshot } from "../../types/dashboard";
import { DataStateNotice } from "../DataStateNotice";
import { SectionPanel } from "../SectionPanel";
import { StatusBadge } from "../StatusBadge";
import { WardMap } from "../WardMap";

interface OverviewPanelsProps {
  snapshot: DashboardSnapshot;
  onSelectWard: (wardId: string) => void;
}

export function OverviewPanels({ snapshot, onSelectWard }: OverviewPanelsProps) {
  const { location, wardContext } = snapshot;

  return (
    <>
      <SectionPanel
        number="01"
        title="Ward GIS Overview"
        eyebrow="Spatial operations"
        status={<StatusBadge>Demo geometry</StatusBadge>}
        className="panel-map"
      >
        <WardMap regions={snapshot.wardRegions} onSelectWard={onSelectWard} />
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
