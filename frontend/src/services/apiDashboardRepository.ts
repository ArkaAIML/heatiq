import type { DashboardRepository } from "./dashboardRepository";
import type {
  DashboardSnapshot,
  PresentedValue,
  WardOption,
  WardRegion,
  WardSeverityState,
} from "../types/dashboard";

interface BackendThermal {
  heat_index_c?: unknown;
  utci_c?: unknown;
  wbgt_c?: unknown;
  htsi?: unknown;
}

interface BackendPrediction {
  prediction_generated_at?: unknown;
  forecast_for?: unknown;
  forecast_horizon_days?: unknown;
  model_name?: unknown;
  model_version?: unknown;
  predicted_max_temperature_c?: unknown;
}

interface BackendInfoPool {
  population?: unknown;
}

interface BackendResourcePool {
  hospital_count?: unknown;
  cooling_centre_count?: unknown;
}

interface BackendWardContext {
  thermal?: BackendThermal | null;
  prediction?: BackendPrediction | null;
  info_pool?: BackendInfoPool | null;
  resource_pool?: BackendResourcePool | null;
}

interface BackendWardResult {
  area_id: string;
  timestamp?: unknown;
  severity?: unknown;
  message?: unknown;
  condition_message?: unknown;
  recommended_actions?: unknown;
  triggered_conditions?: unknown;
  method_version?: unknown;
  context?: BackendWardContext | null;
}

interface ApiDashboardRepositoryOptions {
  apiKey?: string;
  endpoint?: string;
  fetcher?: typeof fetch;
}

const INITIAL_WARD: WardOption = { wardId: "WARD_001", wardName: "Ward 001" };

const MAP_GEOMETRY = [
  { wardId: "WARD_005", points: "45,48 226,34 242,151 72,173", labelX: 139, labelY: 101 },
  { wardId: "WARD_012", points: "226,34 424,52 405,174 242,151", labelX: 326, labelY: 101 },
  { wardId: "WARD_018", points: "424,52 592,83 570,195 405,174", labelX: 498, labelY: 119 },
  { wardId: "WARD_027", points: "72,173 242,151 274,321 91,306", labelX: 170, labelY: 237 },
  { wardId: "WARD_034", points: "242,151 405,174 570,195 536,315 274,321", labelX: 395, labelY: 246 },
] as const;

function wardName(areaId: string): string {
  const match = /^WARD_(\d+)$/.exec(areaId);
  return match ? `Ward ${match[1]}` : areaId;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function availableNumber(value: unknown, unit: string | undefined, note: string): PresentedValue<number> {
  const parsed = numberValue(value);
  return parsed === null
    ? { value: null, state: "unavailable", unit, note: "Not supplied by the backend" }
    : { value: parsed, state: "available", unit, note };
}

function unavailableNumber(note: string, unit?: string): PresentedValue<number> {
  return { value: null, state: "unavailable", unit, note };
}

function severityState(value: unknown): WardSeverityState {
  const normalized = stringValue(value)?.toLowerCase().replaceAll("_", "-");
  const known: WardSeverityState[] = [
    "low", "moderate", "high", "very-high", "severe", "critical", "extreme",
  ];
  return known.includes(normalized as WardSeverityState)
    ? normalized as WardSeverityState
    : "no-data";
}

function wardRegions(results: readonly BackendWardResult[], selectedWardId: string): WardRegion[] {
  const byId = new Map(results.map((result) => [result.area_id, result]));
  return MAP_GEOMETRY.flatMap((geometry) => {
    const result = byId.get(geometry.wardId);
    return result ? [{
      ...geometry,
      wardName: wardName(result.area_id),
      severity: severityState(result.severity),
      selected: result.area_id === selectedWardId,
    }] : [];
  });
}

function responseResults(payload: unknown): BackendWardResult[] {
  if (typeof payload !== "object" || payload === null || !("results" in payload)) {
    throw new Error("Backend response does not contain ward results");
  }
  const results = (payload as { results?: unknown }).results;
  if (!Array.isArray(results)) {
    throw new Error("Backend response ward results are invalid");
  }
  const valid = results.filter((result): result is BackendWardResult => (
    typeof result === "object"
    && result !== null
    && "area_id" in result
    && typeof result.area_id === "string"
  ));
  if (valid.length === 0) {
    throw new Error("Backend returned no usable ward results");
  }
  return valid;
}

function buildSnapshot(result: BackendWardResult, results: readonly BackendWardResult[]): DashboardSnapshot {
  const context = result.context;
  const thermal = context?.thermal;
  const prediction = context?.prediction;
  const resources = context?.resource_pool;
  const info = context?.info_pool;
  const timestamp = stringValue(result.timestamp) ?? stringValue(prediction?.prediction_generated_at) ?? "";
  const predictionContractMatches = (
    stringValue(prediction?.model_name)?.toLowerCase() === "linear_regression"
    && stringValue(prediction?.model_version)?.toLowerCase() === "v1"
    && numberValue(prediction?.forecast_horizon_days) === 1
  );
  const predictionValue = predictionContractMatches
    ? prediction?.predicted_max_temperature_c
    : null;
  const actions = stringList(result.recommended_actions);
  const severity = stringValue(result.severity);

  return {
    dataMode: "live",
    sourceLabel: "HeatIQ backend · /api/process",
    freshness: "current",
    generatedAt: stringValue(prediction?.prediction_generated_at) ?? timestamp,
    location: {
      wardId: result.area_id,
      wardName: wardName(result.area_id),
      city: "Bhubaneswar",
      district: "Unavailable",
      state: "Unavailable",
    },
    wardRegions: wardRegions(results, result.area_id),
    currentWeather: {
      observedAt: timestamp,
      airTemperature: unavailableNumber("Raw weather is not supplied by /api/process", "°C"),
      relativeHumidity: unavailableNumber("Raw weather is not supplied by /api/process", "%"),
      windSpeed: unavailableNumber("Raw weather is not supplied by /api/process", "m/s"),
      surfacePressure: unavailableNumber("Raw weather is not supplied by /api/process", "Pa"),
      rainfall: unavailableNumber("Raw weather is not supplied by /api/process", "mm"),
    },
    thermalStress: {
      calculatedAt: timestamp,
      heatIndex: availableNumber(thermal?.heat_index_c, "°C", "Deterministic backend output"),
      utci: availableNumber(thermal?.utci_c, "°C", "Deterministic backend output"),
      wbgt: availableNumber(thermal?.wbgt_c, "°C", "Deterministic backend output"),
      htsi: availableNumber(thermal?.htsi, undefined, "Backend HTSI output · Not ML"),
    },
    temperatureForecast: {
      modelName: "Linear Regression",
      modelVersion: "v1",
      target: "target_temperature_max_c_d1",
      meaning: "D+1 maximum air temperature",
      unit: "degC",
      forecastHorizonDays: 1,
      featureDate: null,
      forecastDate: stringValue(prediction?.forecast_for),
      generatedAt: stringValue(prediction?.prediction_generated_at) ?? timestamp,
      prediction: availableNumber(
        predictionValue,
        "degC",
        predictionContractMatches
          ? "Backend Linear Regression v1 output"
          : "Backend prediction contract did not match Linear Regression v1, D+1",
      ),
    },
    dangerousHours: {
      state: "unavailable",
      startTime: null,
      endTime: null,
      severity: null,
      sourceLabel: "Backend dangerous-hours output unavailable",
      note: "No dangerous-hours assessment is supplied by /api/process; it is not derived from the D+1 prediction.",
    },
    wardContext: {
      heatSeverity: severity === null
        ? { value: null, state: "unavailable", note: "Backend severity was not supplied" }
        : { value: severity, state: "available", note: "Backend ward severity" },
      population: availableNumber(info?.population, "people", "Backend ward context"),
      vulnerableGroups: {
        value: null,
        state: "unavailable",
        note: "No vulnerable-group list is supplied by /api/process",
      },
      coolingFacilities: availableNumber(resources?.cooling_centre_count, "facilities", "Backend resource context"),
      healthFacilities: availableNumber(resources?.hospital_count, "facilities", "Backend resource context"),
      waterPoints: unavailableNumber("No water-point inventory is supplied by /api/process"),
    },
    advisory: {
      state: actions.length > 0 ? "available" : "unavailable",
      reference: stringValue(result.method_version),
      title: stringValue(result.condition_message) ?? stringValue(result.message) ?? "Advisory unavailable",
      actions,
      reasonCodes: stringList(result.triggered_conditions),
    },
    citizenWarning: {
      state: "unavailable",
      headline: "Citizen warning unavailable",
      message: "No citizen-warning message is supplied by /api/process.",
      validFrom: null,
      validUntil: null,
    },
  };
}

export function createApiDashboardRepository(
  options: ApiDashboardRepositoryOptions = {},
): DashboardRepository {
  const apiKey = options.apiKey ?? import.meta.env.VITE_HEATIQ_API_KEY;
  const endpoint = options.endpoint ?? "/api/process";
  const fetcher = options.fetcher ?? fetch;
  const optionsList: WardOption[] = [INITIAL_WARD];
  let cachedResults: BackendWardResult[] | null = null;
  let inFlight: Promise<BackendWardResult[]> | null = null;

  async function loadResults(): Promise<BackendWardResult[]> {
    if (cachedResults) return cachedResults;
    if (!apiKey) {
      throw new Error("VITE_HEATIQ_API_KEY is not configured");
    }
    if (!inFlight) {
      inFlight = fetcher(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify({ location: "Bhubaneswar" }),
      }).then(async (response) => {
        if (!response.ok) {
          throw new Error(`HeatIQ backend request failed with HTTP ${response.status}`);
        }
        const results = responseResults(await response.json());
        cachedResults = results;
        optionsList.splice(0, optionsList.length, ...results.map((result) => ({
          wardId: result.area_id,
          wardName: wardName(result.area_id),
        })));
        return results;
      }).finally(() => {
        inFlight = null;
      });
    }
    return inFlight;
  }

  return {
    wardOptions: optionsList,
    async getSnapshot(wardId: string): Promise<DashboardSnapshot> {
      const results = await loadResults();
      const selected = results.find((result) => result.area_id === wardId) ?? results[0];
      if (!selected) throw new Error("Selected ward is unavailable");
      return buildSnapshot(selected, results);
    },
    refresh(): void {
      cachedResults = null;
    },
  };
}

export const apiDashboardRepository = createApiDashboardRepository();
