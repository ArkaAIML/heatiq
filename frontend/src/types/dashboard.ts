export type DataMode = "demonstration" | "live";
export type FreshnessState = "current" | "stale";
export type PresentedValueState =
  | "available"
  | "demonstration"
  | "stale"
  | "unavailable";

export interface PresentedValue<T> {
  value: T | null;
  state: PresentedValueState;
  unit?: string;
  note?: string;
}

export interface DashboardLocation {
  wardId: string;
  wardName: string;
  city: string;
  district: string;
  state: string;
}

export interface CurrentWeather {
  observedAt: string;
  airTemperature: PresentedValue<number>;
  relativeHumidity: PresentedValue<number>;
  windSpeed: PresentedValue<number>;
  surfacePressure: PresentedValue<number>;
  rainfall: PresentedValue<number>;
}

export interface ThermalStress {
  calculatedAt: string;
  heatIndex: PresentedValue<number>;
  utci: PresentedValue<number>;
  wbgt: PresentedValue<number>;
}

export interface TemperatureForecast {
  modelName: "Linear Regression";
  modelVersion: "v1";
  target: "target_temperature_max_c_d1";
  meaning: "D+1 maximum air temperature";
  unit: "degC";
  forecastHorizonDays: 1;
  featureDate: string;
  forecastDate: string;
  generatedAt: string;
  prediction: PresentedValue<number>;
}

export type OperationalSeverity =
  | "moderate"
  | "high"
  | "very-high"
  | "severe";

export interface DangerousHours {
  state: "demonstration" | "stale" | "unavailable";
  startTime: string | null;
  endTime: string | null;
  severity: OperationalSeverity | null;
  sourceLabel: string;
  note: string;
}

export interface WardContext {
  heatSeverity: PresentedValue<string>;
  population: PresentedValue<number>;
  vulnerableGroups: PresentedValue<string[]>;
  coolingFacilities: PresentedValue<number>;
  healthFacilities: PresentedValue<number>;
  waterPoints: PresentedValue<number>;
}

export interface Advisory {
  state: "demonstration" | "stale" | "unavailable";
  reference: string | null;
  title: string;
  actions: string[];
  reasonCodes: string[];
}

export interface CitizenWarning {
  state: "demonstration" | "stale" | "unavailable";
  headline: string;
  message: string;
  validFrom: string | null;
  validUntil: string | null;
}

export interface DashboardSnapshot {
  dataMode: DataMode;
  sourceLabel: string;
  freshness: FreshnessState;
  generatedAt: string;
  location: DashboardLocation;
  currentWeather: CurrentWeather;
  thermalStress: ThermalStress;
  temperatureForecast: TemperatureForecast;
  dangerousHours: DangerousHours;
  wardContext: WardContext;
  advisory: Advisory;
  citizenWarning: CitizenWarning;
}

export type DashboardRequestState =
  | { status: "loading" }
  | { status: "ready"; snapshot: DashboardSnapshot }
  | { status: "error"; message: string };
