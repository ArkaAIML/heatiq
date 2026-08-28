import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";
import { createMockDashboardRepository } from "./services/mockDashboardRepository";

const fastRepository = createMockDashboardRepository({ delayMs: 0 });

describe("HeatIQ control-room dashboard", () => {
  it("renders loading and then clearly labelled demonstration data", async () => {
    render(<App repository={fastRepository} />);

    expect(screen.getByText("Loading dashboard")).toBeInTheDocument();
    expect(await screen.findByText("38.4")).toBeInTheDocument();
    expect(screen.getByText("Demonstration interface")).toBeInTheDocument();
    expect(screen.getAllByText(/Demo data|Demonstration data/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
  });

  it("preserves the deployed model semantics and separate danger window", async () => {
    render(<App repository={fastRepository} />);

    expect(await screen.findByText("D+1 Maximum Air Temperature")).toBeInTheDocument();
    expect(screen.getByText("target_temperature_max_c_d1")).toBeInTheDocument();
    expect(screen.getAllByText("Linear Regression v1").length).toBeGreaterThan(0);
    expect(screen.getByText("D+1 maximum air temperature")).toBeInTheDocument();
    expect(screen.getByText("11:00–15:00")).toBeInTheDocument();
    expect(screen.getAllByText(/not derived from the D\+1 model/)).toHaveLength(2);
    expect(screen.queryByText("UTCI prediction")).not.toBeInTheDocument();
    expect(screen.queryByText("Heat-risk score")).not.toBeInTheDocument();
  });

  it("updates the selected demo ward through the repository", async () => {
    render(<App repository={fastRepository} />);
    await screen.findByText("Ward 12 · Demo data");

    const selector = screen.getByLabelText("Ward / administrative area");
    expect(selector).toHaveValue("ward-12");
    expect(screen.getByRole("button", { name: /Ward 12, very high/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    fireEvent.change(selector, {
      target: { value: "ward-27" },
    });

    expect(await screen.findByText("Ward 27 · Demo data")).toBeInTheDocument();
    expect(selector).toHaveValue("ward-27");
    expect(screen.getByRole("button", { name: /Ward 27, severe/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("synchronizes map selection back to the ward selector", async () => {
    render(<App repository={fastRepository} />);
    await screen.findByText("Ward 12 · Demo data");

    fireEvent.click(screen.getByRole("button", { name: /Ward 34, no data/i }));

    expect(await screen.findByText("Ward 34 · Demo data")).toBeInTheDocument();
    expect(screen.getByLabelText("Ward / administrative area")).toHaveValue("ward-34");
    expect(screen.getByRole("button", { name: /Ward 34, no data/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("renders stale snapshots as unsafe to treat as current", async () => {
    const staleRepository = createMockDashboardRepository({
      delayMs: 0,
      freshness: "stale",
    });

    render(<App repository={staleRepository} />);

    expect(await screen.findAllByText("Stale demonstration data")).not.toHaveLength(0);
    expect(screen.getByText(/Do not treat it as current operational information/)).toBeInTheDocument();
  });

  it("renders repository failures with an explicit error state", async () => {
    const failingRepository = createMockDashboardRepository({
      delayMs: 0,
      shouldFail: true,
    });

    render(<App repository={failingRepository} />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Unable to load dashboard");
    expect(alert).toHaveTextContent("Demonstration repository failed to load");
  });

  it("associates every dashboard region with a unique heading", async () => {
    const { container } = render(<App repository={fastRepository} />);
    await screen.findByText("Ward GIS Overview");
    const labelledSections = Array.from(
      container.querySelectorAll("section[aria-labelledby]"),
    );
    const headingIds = labelledSections.map((section) =>
      section.getAttribute("aria-labelledby"),
    );

    expect(new Set(headingIds).size).toBe(headingIds.length);
    for (const headingId of headingIds) {
      expect(container.querySelector(`#${headingId}`)).toBeInTheDocument();
    }
  });
});
