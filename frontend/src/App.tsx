import { useCallback, useEffect, useState } from "react";

import { ConditionsPanels } from "./components/dashboard/ConditionsPanels";
import { OverviewPanels } from "./components/dashboard/OverviewPanels";
import { ResponsePanels } from "./components/dashboard/ResponsePanels";
import { ControlBar } from "./components/ControlBar";
import { DataStateNotice } from "./components/DataStateNotice";
import { SystemHeader } from "./components/SystemHeader";
import type { DashboardRepository } from "./services/dashboardRepository";
import { mockDashboardRepository } from "./services/mockDashboardRepository";
import type { DashboardRequestState } from "./types/dashboard";

interface AppProps {
  repository?: DashboardRepository;
}

function formatUpdatedAt(value: string): string {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return "Invalid timestamp";
  }
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(timestamp);
}

function App({ repository = mockDashboardRepository }: AppProps) {
  const defaultWard = repository.wardOptions.find((option) => option.wardId === "ward-12")
    ?? repository.wardOptions[0];
  const [ward, setWard] = useState(defaultWard?.wardId ?? "all");
  const [refreshSequence, setRefreshSequence] = useState(0);
  const [request, setRequest] = useState<DashboardRequestState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    setRequest((current) => ({
      status: "loading",
      previousSnapshot: current.status === "ready"
        ? current.snapshot
        : current.status === "loading"
          ? current.previousSnapshot
          : undefined,
    }));

    void repository.getSnapshot(ward).then(
      (snapshot) => {
        if (active) {
          setRequest({ status: "ready", snapshot });
        }
      },
      (error: unknown) => {
        if (active) {
          const message = error instanceof Error ? error.message : "Unknown dashboard error";
          setRequest((current) => ({
            status: "error",
            message,
            previousSnapshot: current.status === "loading"
              ? current.previousSnapshot
              : undefined,
          }));
        }
      },
    );

    return () => {
      active = false;
    };
  }, [refreshSequence, repository, ward]);

  const refresh = useCallback(() => {
    setRefreshSequence((sequence) => sequence + 1);
  }, []);

  const snapshot = request.status === "ready"
    ? request.snapshot
    : request.status === "loading"
      ? request.previousSnapshot ?? null
      : request.previousSnapshot ?? null;
  const isLoading = request.status === "loading";
  const isRefreshing = isLoading && snapshot !== null;
  const headerState = request.status === "loading"
    ? "loading"
    : request.status === "error"
      ? "error"
      : snapshot?.freshness === "stale"
        ? "stale"
        : "demonstration";

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to dashboard content</a>
      <SystemHeader
        operationalArea={snapshot ? `${snapshot.location.city} · Demonstration` : "Bhubaneswar · Demonstration"}
        updatedLabel={snapshot ? formatUpdatedAt(snapshot.generatedAt) : "Awaiting demo data"}
        state={headerState}
      />

      <main
        id="main-content"
        className="dashboard-container"
        tabIndex={-1}
        aria-busy={isLoading}
      >
        <ControlBar
          ward={ward}
          onWardChange={setWard}
          onRefresh={refresh}
          isLoading={isLoading}
          sourceLabel={snapshot?.sourceLabel ?? "HeatIQ demonstration repository"}
          wardOptions={repository.wardOptions}
        />

        <aside className="demo-notice" aria-label="Demonstration data notice">
          <strong>Demonstration interface</strong>
          <span>All populated values are non-live demonstration data. Missing scientific outputs remain explicitly unavailable.</span>
        </aside>

        {isLoading ? (
          <div className={isRefreshing ? "dashboard-message dashboard-message--inline" : "dashboard-message"}>
            <DataStateNotice
              state="loading"
              title={isRefreshing ? "Refreshing dashboard" : "Loading dashboard"}
            >
              {isRefreshing
                ? "The previous demonstration snapshot remains visible until refresh completes."
                : "Retrieving the selected demonstration snapshot."}
            </DataStateNotice>
          </div>
        ) : null}

        {request.status === "error" ? (
          <div className={snapshot ? "dashboard-message dashboard-message--inline" : "dashboard-message"}>
            <DataStateNotice state="error" title="Unable to load dashboard">
              {request.message}. {snapshot
                ? "The previous demonstration snapshot remains visible; use Refresh data to try again."
                : "Use Refresh data to try again."}
            </DataStateNotice>
          </div>
        ) : null}

        {snapshot?.freshness === "stale" ? (
          <DataStateNotice state="stale" title="Stale demonstration data">
            The repository marked this snapshot as stale. Do not treat it as current operational information.
          </DataStateNotice>
        ) : null}

        {snapshot ? (
          <div className="dashboard-grid">
            <OverviewPanels snapshot={snapshot} onSelectWard={setWard} />
            <ConditionsPanels snapshot={snapshot} />
            <ResponsePanels snapshot={snapshot} />
          </div>
        ) : null}
      </main>

      <footer className="system-footer">
        <span>HeatIQ · Smart India Hackathon prototype</span>
        <span>Decision support only · Not an official Government of India service</span>
      </footer>
    </div>
  );
}

export default App;
