import { describe, expect, it, vi } from "vitest";

import { createApiDashboardRepository } from "./apiDashboardRepository";

function backendWard(index: number) {
  const areaId = `WARD_${String(index).padStart(3, "0")}`;
  return {
    area_id: areaId,
    timestamp: "2026-08-29T01:45Z",
    severity: index === 12 ? "HIGH" : "LOW",
    message: "Highest risk condition: BASELINE.",
    condition_message: "Routine vigilance advised.",
    recommended_actions: ["Maintain routine vigilance."],
    triggered_conditions: ["BASELINE"],
    method_version: "WARD_FILTER_MVP",
    context: {
      thermal: {
        heat_index_c: 32.94,
        utci_c: 26.05,
        wbgt_c: 26.56,
        htsi: 27.53,
      },
      prediction: {
        prediction_generated_at: "2026-08-29T01:55:21Z",
        forecast_for: "2026-08-30",
        forecast_horizon_days: 1,
        model_name: "linear_regression",
        model_version: "v1",
        predicted_max_temperature_c: 34.49693632560489,
      },
      info_pool: { population: index === 12 ? null : 10_000 + index },
      resource_pool: { hospital_count: 2, cooling_centre_count: 1 },
    },
  };
}

function successfulResponse() {
  return {
    ok: true,
    status: 200,
    json: async () => ({
      request_id: "request-1",
      status: "success",
      route: "PLACE_NAME",
      results: Array.from({ length: 60 }, (_, index) => backendWard(index + 1)),
    }),
  } as Response;
}

describe("ApiDashboardRepository", () => {
  it("loads all wards and maps backend scientific fields without filling nulls", async () => {
    const fetcher = vi.fn().mockResolvedValue(successfulResponse());
    const repository = createApiDashboardRepository({ apiKey: "development-key", fetcher });

    const snapshot = await repository.getSnapshot("WARD_012");

    expect(fetcher).toHaveBeenCalledWith("/api/process", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": "development-key",
      },
      body: JSON.stringify({ location: "Bhubaneswar" }),
    });
    expect(repository.wardOptions).toHaveLength(60);
    expect(snapshot.location.wardId).toBe("WARD_012");
    expect(snapshot.wardRegions).toHaveLength(5);
    expect(snapshot.wardRegions.find((ward) => ward.wardId === "WARD_012")?.selected).toBe(true);
    expect(snapshot.temperatureForecast.prediction.value).toBe(34.49693632560489);
    expect(snapshot.temperatureForecast.target).toBe("target_temperature_max_c_d1");
    expect(snapshot.temperatureForecast.meaning).toBe("D+1 maximum air temperature");
    expect(snapshot.thermalStress.heatIndex.value).toBe(32.94);
    expect(snapshot.thermalStress.utci.value).toBe(26.05);
    expect(snapshot.thermalStress.wbgt.value).toBe(26.56);
    expect(snapshot.thermalStress.htsi.value).toBe(27.53);
    expect(snapshot.wardContext.population.value).toBeNull();
    expect(snapshot.wardContext.population.state).toBe("unavailable");
    expect(snapshot.currentWeather.airTemperature.value).toBeNull();
    expect(snapshot.dangerousHours.state).toBe("unavailable");
    expect(snapshot.citizenWarning.state).toBe("unavailable");
  });

  it("reports authentication and HTTP failures instead of using mock data", async () => {
    const missingKeyRepository = createApiDashboardRepository({ apiKey: "" });
    await expect(missingKeyRepository.getSnapshot("WARD_001")).rejects.toThrow(
      "VITE_HEATIQ_API_KEY is not configured",
    );

    const fetcher = vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response);
    const rejectedRepository = createApiDashboardRepository({ apiKey: "bad-key", fetcher });
    await expect(rejectedRepository.getSnapshot("WARD_001")).rejects.toThrow("HTTP 401");
  });
});
