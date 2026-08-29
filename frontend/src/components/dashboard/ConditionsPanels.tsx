import type { DashboardSnapshot, PresentedValue } from "../../types/dashboard";
import { DataValue } from "../DataValue";
import { SectionPanel } from "../SectionPanel";
import { StatusBadge } from "../StatusBadge";

interface ConditionsPanelsProps {
  snapshot: DashboardSnapshot;
}

function formatPrediction(value: PresentedValue<number>): string {
  return value.value === null ? "Unavailable" : value.value.toFixed(1);
}

export function ConditionsPanels({ snapshot }: ConditionsPanelsProps) {
  const { currentWeather, thermalStress, temperatureForecast } = snapshot;

  return (
    <>
      <SectionPanel
        number="02"
        title="Current Weather"
        eyebrow="Observed conditions · Demo repository"
        status={<StatusBadge>Demo data</StatusBadge>}
        className="panel-weather"
      >
        <dl className="metric-grid">
          <DataValue label="Air temperature" data={currentWeather.airTemperature} />
          <DataValue label="Relative humidity" data={currentWeather.relativeHumidity} />
          <DataValue label="Wind speed" data={currentWeather.windSpeed} />
          <DataValue label="Surface pressure" data={currentWeather.surfacePressure} />
        </dl>
      </SectionPanel>

      <SectionPanel
        number="03"
        title="Thermal Stress"
        eyebrow="Deterministic indices · Demo repository"
        status={<StatusBadge>Mixed availability</StatusBadge>}
        className="panel-thermal"
      >
        <dl className="metric-grid metric-grid--three">
          <DataValue label="Heat Index" data={thermalStress.heatIndex} />
          <DataValue label="UTCI" data={thermalStress.utci} />
          <DataValue label="WBGT" data={thermalStress.wbgt} />
        </dl>
      </SectionPanel>

      <SectionPanel
        number="04"
        title="D+1 Maximum Air Temperature"
        eyebrow={`ML forecast · ${temperatureForecast.modelName} ${temperatureForecast.modelVersion}`}
        status={<StatusBadge>Demo prediction</StatusBadge>}
        className="panel-forecast"
      >
        <div className="forecast-reading" data-state={temperatureForecast.prediction.state}>
          <span>Forecast value</span>
          <strong>{formatPrediction(temperatureForecast.prediction)}</strong>
          <small>{temperatureForecast.unit} · {temperatureForecast.forecastHorizonDays}-day horizon · Demo output</small>
        </div>
        <dl className="model-contract">
          <div><dt>Meaning</dt><dd>{temperatureForecast.meaning}</dd></div>
          <div><dt>Target</dt><dd>{temperatureForecast.target}</dd></div>
          <div><dt>Model</dt><dd>{temperatureForecast.modelName} {temperatureForecast.modelVersion}</dd></div>
          <div><dt>Feature date</dt><dd>{temperatureForecast.featureDate}</dd></div>
          <div><dt>Forecast date</dt><dd>{temperatureForecast.forecastDate}</dd></div>
          <div><dt>Generated at</dt><dd>{temperatureForecast.generatedAt}</dd></div>
        </dl>
      </SectionPanel>
    </>
  );
}
