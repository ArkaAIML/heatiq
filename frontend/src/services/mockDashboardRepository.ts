import type { DashboardRepository } from "./dashboardRepository";
import type {
  DashboardLocation,
  DashboardSnapshot,
  FreshnessState,
  PresentedValue,
} from "../types/dashboard";

interface MockRepositoryOptions {
  delayMs?: number;
  freshness?: FreshnessState;
  shouldFail?: boolean;
}

const DEMO_GENERATED_AT = "2026-08-28T12:30:00+05:30";

const locations: Record<string, DashboardLocation> = {
  all: {
    wardId: "all",
    wardName: "All wards",
    city: "Bhubaneswar",
    district: "Khordha",
    state: "Odisha",
  },
  "ward-12": {
    wardId: "ward-12",
    wardName: "Ward 12",
    city: "Bhubaneswar",
    district: "Khordha",
    state: "Odisha",
  },
  "ward-27": {
    wardId: "ward-27",
    wardName: "Ward 27",
    city: "Bhubaneswar",
    district: "Khordha",
    state: "Odisha",
  },
};

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
  const location = locations[wardId] ?? locations.all;
  const stale = freshness === "stale";
  const operationalState = stale ? "stale" : "demonstration";

  return {
    dataMode: "demonstration",
    sourceLabel: "HeatIQ demonstration repository",
    freshness,
    generatedAt: DEMO_GENERATED_AT,
    location,
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
      heatSeverity: demoValue("Very high", undefined, "Demonstration operational classification"),
      population: demoValue(31_450, "people"),
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
