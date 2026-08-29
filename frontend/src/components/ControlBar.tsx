import type { DataMode, WardOption } from "../types/dashboard";

interface ControlBarProps {
  ward: string;
  onWardChange: (ward: string) => void;
  onRefresh: () => void;
  isLoading: boolean;
  sourceLabel: string;
  wardOptions: readonly WardOption[];
  dataMode: DataMode;
}

export function ControlBar({
  ward,
  onWardChange,
  onRefresh,
  isLoading,
  sourceLabel,
  wardOptions,
  dataMode,
}: ControlBarProps) {
  return (
    <section className="control-bar" aria-label="Dashboard controls">
      <div className="control-bar__field">
        <label htmlFor="ward-select">Ward / administrative area</label>
        <select
          id="ward-select"
          value={ward}
          disabled={wardOptions.length === 0 || isLoading}
          aria-describedby="ward-select-help"
          onChange={(event) => onWardChange(event.target.value)}
        >
          {wardOptions.length === 0 ? (
            <option value="all">{dataMode === "demonstration"
              ? "No demonstration wards available"
              : "No wards available"}</option>
          ) : (
            wardOptions.map((option) => (
              <option key={option.wardId} value={option.wardId}>
                {option.wardName}{dataMode === "demonstration"
                  ? ` · ${option.wardId === "all" ? "Demo view" : "Demo selection"}`
                  : ""}
              </option>
            ))
          )}
        </select>
        <span className="control-bar__help" id="ward-select-help">
          {dataMode === "demonstration" ? "Demonstration" : "Backend"} administrative selection
        </span>
      </div>
      <div className="control-bar__readout">
        <span className="control-bar__label">Data source</span>
        <strong>{sourceLabel}</strong>
      </div>
      <div className="control-bar__readout">
        <span className="control-bar__label">Refresh cycle</span>
        <strong>Manual · {dataMode === "demonstration" ? "Demo repository" : "Backend API"}</strong>
      </div>
      <button type="button" onClick={onRefresh} disabled={isLoading} aria-busy={isLoading}>
        {isLoading ? "Refreshing data…" : "Refresh data"}
      </button>
    </section>
  );
}
