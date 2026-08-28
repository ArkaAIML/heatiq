interface ControlBarProps {
  ward: string;
  onWardChange: (ward: string) => void;
}

export function ControlBar({ ward, onWardChange }: ControlBarProps) {
  return (
    <section className="control-bar" aria-label="Dashboard controls">
      <div className="control-bar__field">
        <label htmlFor="ward-select">Ward / administrative area</label>
        <select
          id="ward-select"
          value={ward}
          onChange={(event) => onWardChange(event.target.value)}
        >
          <option value="all">All wards · Demo view</option>
          <option value="ward-12">Ward 12 · Demo selection</option>
          <option value="ward-27">Ward 27 · Demo selection</option>
        </select>
      </div>
      <div className="control-bar__readout">
        <span className="control-bar__label">Data source</span>
        <strong>Frontend demonstration dataset</strong>
      </div>
      <div className="control-bar__readout">
        <span className="control-bar__label">Refresh cycle</span>
        <strong>Not connected</strong>
      </div>
      <button type="button" disabled title="Live API connection is not configured">
        Refresh data
      </button>
    </section>
  );
}
