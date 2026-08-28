import { describe, expect, it } from "vitest";

import {
  buildMockDashboardSnapshot,
  createMockDashboardRepository,
} from "./mockDashboardRepository";

describe("mock dashboard repository", () => {
  it("returns a visibly demonstrative snapshot with explicit unavailable fields", async () => {
    const repository = createMockDashboardRepository({ delayMs: 0 });

    const snapshot = await repository.getSnapshot("ward-12");

    expect(snapshot.dataMode).toBe("demonstration");
    expect(snapshot.sourceLabel).toContain("demonstration");
    expect(snapshot.location.wardName).toBe("Ward 12");
    expect(snapshot.thermalStress.wbgt).toMatchObject({
      value: null,
      state: "unavailable",
    });
    expect(snapshot.wardContext.waterPoints.value).toBeNull();
  });

  it("locks the deployment forecast contract and keeps danger hours separate", () => {
    const snapshot = buildMockDashboardSnapshot("all");

    expect(snapshot.temperatureForecast).toMatchObject({
      modelName: "Linear Regression",
      modelVersion: "v1",
      target: "target_temperature_max_c_d1",
      meaning: "D+1 maximum air temperature",
      unit: "degC",
      forecastHorizonDays: 1,
    });
    expect(snapshot.temperatureForecast.prediction.state).toBe("demonstration");
    expect(snapshot.dangerousHours.sourceLabel).toBe("Mock dangerous-hours service");
    expect(snapshot.dangerousHours).not.toHaveProperty("modelName");
    expect(snapshot.dangerousHours).not.toHaveProperty("target");
  });
});
