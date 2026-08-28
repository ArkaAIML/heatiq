import type { WardOption } from "../types/dashboard";

interface ControlBarProps {
  ward: string;
  onWardChange: (ward: string) => void;
  onRefresh: () => void;
  isLoading: boolean;
  sourceLabel: string;
  wardOptions: readonly WardOption[];
}

export function ControlBar({
  ward,
  onWardChange,
  onRefresh,
  isLoading,
  sourceLabel,
  wardOptions,
}: ControlBarProps) {
  return (
    <section className="control-bar" aria-label="Dashboard controls">
      <div className="control-bar__field">
        <label htmlFor="ward-select">Ward / administrative area</label>
        <select
          id="ward-select"
          value={ward}
          onChange={(event) => onWardChange(event.target.value)}
        >
          {wardOptions.map((option) => (
            <option key={option.wardId} value={option.wardId}>
              {option.wardName} · {option.wardId === "all" ? "Demo view" : "Demo selection"}
            </option>
          ))}
        </select>
      </div>
      <div className="control-bar__readout">
        <span className="control-bar__label">Data source</span>
        <strong>{sourceLabel}</strong>
      </div>
      <div className="control-bar__readout">
        <span className="control-bar__label">Refresh cycle</span>
        <strong>Manual · Demo repository</strong>
      </div>
      <button type="button" onClick={onRefresh} disabled={isLoading}>
        {isLoading ? "Loading…" : "Refresh data"}
      </button>
    </section>
  );
}
