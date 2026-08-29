import type { DashboardRepository } from "./dashboardRepository";
import type {
  DashboardLocation,
  DashboardSnapshot,
  FreshnessState,
  PresentedValue,
  WardRegion,
} from "../types/dashboard";

interface MockRepositoryOptions {
  delayMs?: number;
  freshness?: FreshnessState;
  shouldFail?: boolean;
}

const DEMO_GENERATED_AT = "2026-08-28T12:30:00+05:30";

interface DemoWardDefinition extends DashboardLocation {
  severity: WardRegion["severity"];
  severityLabel: string;
  population: number;
  points: string;
  labelX: number;
  labelY: number;
}

const aggregateLocation: DashboardLocation = {
  wardId: "all",
  wardName: "All wards",
  city: "Bhubaneswar",
  district: "Khordha",
  state: "Odisha",
};

const demoWards: DemoWardDefinition[] = [
  {
    wardId: "ward-05", wardName: "Ward 05", city: "Bhubaneswar", district: "Khordha", state: "Odisha",
    severity: "moderate", severityLabel: "Moderate", population: 28_620,
    points: "45,48 226,34 242,151 72,173", labelX: 139, labelY: 101,
  },
  {
    wardId: "ward-12", wardName: "Ward 12", city: "Bhubaneswar", district: "Khordha", state: "Odisha",
    severity: "very-high", severityLabel: "Very high", population: 31_450,
    points: "226,34 424,52 405,174 242,151", labelX: 326, labelY: 101,
  },
  {
    wardId: "ward-18", wardName: "Ward 18", city: "Bhubaneswar", district: "Khordha", state: "Odisha",
    severity: "high", severityLabel: "High", population: 26_880,
    points: "424,52 592,83 570,195 405,174", labelX: 498, labelY: 119,
  },
  {
    wardId: "ward-27", wardName: "Ward 27", city: "Bhubaneswar", district: "Khordha", state: "Odisha",
    severity: "severe", severityLabel: "Severe", population: 34_210,
    points: "72,173 242,151 274,321 91,306", labelX: 170, labelY: 237,
  },
  {
    wardId: "ward-34", wardName: "Ward 34", city: "Bhubaneswar", district: "Khordha", state: "Odisha",
    severity: "no-data", severityLabel: "No data", population: 29_770,
    points: "242,151 405,174 570,195 536,315 274,321", labelX: 395, labelY: 246,
  },
];

export const DEMO_WARD_OPTIONS = [
  { wardId: "all", wardName: "All wards" },
  ...demoWards.map(({ wardId, wardName }) => ({ wardId, wardName })),
];

function buildWardRegions(selectedWardId: string): WardRegion[] {
  return demoWards.map(({ wardId, wardName, severity, points, labelX, labelY }) => ({
    wardId,
    wardName,
    severity,
    points,
    labelX,
    labelY,
    selected: wardId === selectedWardId,
  }));
}

function selectedWard(wardId: string): DemoWardDefinition | undefined {
  return demoWards.find((ward) => ward.wardId === wardId);
}

function demoValue<T>(value: T, unit?: string, note?: string): PresentedValue<T> {
  return { value, state: "demonstration", unit, note: note ?? "Demonstration value" };
}

function unavailableValue<T>(note: string, unit?: string): PresentedValue<T> {
  return { value: null, state: "unavailable", unit, note };
}

export function buildMockDashboardSnapshot(
  wardId: string,
  freshness: FreshnessState = "current",
): DashboardSnapshot {
  const ward = selectedWard(wardId);
  const location = ward ?? aggregateLocation;
  const stale = freshness === "stale";
  const operationalState = stale ? "stale" : "demonstration";

  return {
    dataMode: "demonstration",
    sourceLabel: "HeatIQ demonstration repository",
    freshness,
    generatedAt: DEMO_GENERATED_AT,
    location,
    wardRegions: buildWardRegions(location.wardId),
    currentWeather: {
      observedAt: "2026-08-28T12:00:00+05:30",
      airTemperature: demoValue(36.8, "°C"),
      relativeHumidity: demoValue(58, "%"),
      windSpeed: demoValue(3.2, "m/s"),
      surfacePressure: demoValue(99_740, "Pa"),
      rainfall: unavailableValue("Provider field intentionally unavailable", "mm"),
    },
    thermalStress: {
      calculatedAt: "2026-08-28T12:05:00+05:30",
      heatIndex: demoValue(44.2, "°C", "Demonstration deterministic output"),
      utci: demoValue(42.6, "°C", "Demonstration deterministic output"),
      wbgt: unavailableValue("WBGT is not supplied by the demonstration feed", "°C"),
      htsi: unavailableValue("HTSI is not supplied by the demonstration feed"),
    },
    temperatureForecast: {
      modelName: "Linear Regression",
      modelVersion: "v1",
      target: "target_temperature_max_c_d1",
      meaning: "D+1 maximum air temperature",
      unit: "degC",
      forecastHorizonDays: 1,
      featureDate: "2026-08-28",
      forecastDate: "2026-08-29",
      generatedAt: DEMO_GENERATED_AT,
      prediction: demoValue(38.4, "degC", "Demonstration model output"),
    },
    dangerousHours: {
      state: operationalState,
      startTime: "11:00",
      endTime: "15:00",
      severity: "very-high",
      sourceLabel: "Mock dangerous-hours service",
      note: "Separate demonstration output; not derived from the D+1 model in this interface.",
    },
    wardContext: {
      heatSeverity: demoValue(ward?.severityLabel ?? "Mixed", undefined, "Demonstration operational classification"),
      population: demoValue(ward?.population ?? 150_930, "people"),
      vulnerableGroups: demoValue([
        "Outdoor workers",
        "Older adults",
        "Children",
        "People without reliable cooling",
      ]),
      coolingFacilities: demoValue(4, "facilities"),
      healthFacilities: demoValue(7, "facilities"),
      waterPoints: unavailableValue("No verified water-point inventory"),
    },
    advisory: {
      state: operationalState,
      reference: "HEATIQ / DEMO / 028",
      title: "Demonstration heat preparedness advisory",
      actions: [
        "Schedule outdoor municipal work outside the 11:00–15:00 demonstration window.",
        "Confirm drinking-water availability at listed cooling and health facilities.",
        "Prepare ward-level outreach for older adults and outdoor workers.",
      ],
      reasonCodes: ["DEMO_DANGEROUS_HOURS", "DEMO_THERMAL_STRESS"],
    },
    citizenWarning: {
      state: operationalState,
      headline: "Demonstration heat advisory",
      message:
        "High heat conditions are shown for demonstration purposes. Avoid strenuous outdoor activity during the displayed afternoon window and stay hydrated.",
      validFrom: "2026-08-28T11:00:00+05:30",
      validUntil: "2026-08-28T15:00:00+05:30",
    },
  };
}

export function createMockDashboardRepository(
  options: MockRepositoryOptions = {},
): DashboardRepository {
  const { delayMs = 180, freshness = "current", shouldFail = false } = options;

  return {
    wardOptions: DEMO_WARD_OPTIONS,
    async getSnapshot(wardId: string): Promise<DashboardSnapshot> {
      if (delayMs > 0) {
        await new Promise((resolve) => window.setTimeout(resolve, delayMs));
      }
      if (shouldFail) {
        throw new Error("Demonstration repository failed to load");
      }
      return buildMockDashboardSnapshot(wardId, freshness);
    },
  };
}

export const mockDashboardRepository = createMockDashboardRepository();
