import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("HeatIQ control-room shell", () => {
  it("labels demonstration and unavailable data explicitly", () => {
    render(<App />);

    expect(screen.getByText("Demonstration interface")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.getByText("No public warning generated")).toBeInTheDocument();
  });

  it("preserves the deployed model semantics", () => {
    render(<App />);

    expect(screen.getByText("D+1 Maximum Air Temperature")).toBeInTheDocument();
    expect(screen.getByText("target_temperature_max_c_d1")).toBeInTheDocument();
    expect(screen.getAllByText("Linear Regression v1").length).toBeGreaterThan(0);
    expect(screen.queryByText("UTCI prediction")).not.toBeInTheDocument();
  });

  it("updates the selected demo ward through the labelled control", () => {
    render(<App />);

    fireEvent.change(screen.getByLabelText("Ward / administrative area"), {
      target: { value: "ward-12" },
    });

    expect(screen.getAllByText("Ward 12").length).toBeGreaterThan(0);
  });

  it("associates every dashboard region with a unique heading", () => {
    const { container } = render(<App />);
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
