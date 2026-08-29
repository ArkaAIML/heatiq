import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { buildMockDashboardSnapshot } from "../services/mockDashboardRepository";
import { WardMap } from "./WardMap";

describe("WardMap", () => {
  it("exposes illustrative ward regions with severity and selection semantics", () => {
    const snapshot = buildMockDashboardSnapshot("ward-12");

    render(<WardMap regions={snapshot.wardRegions} onSelectWard={() => undefined} />);

    expect(screen.getByText("Demonstration ward layout")).toBeInTheDocument();
    expect(screen.getByText(/Not authoritative GIS boundaries/)).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Demo severity" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ward Severity" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Heat Intensity" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: /Ward 12, Very high/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Ward 27, Severe/ })).toHaveAttribute("aria-pressed", "false");
  });

  it("switches between severity and demonstration heat intensity layers", () => {
    const snapshot = buildMockDashboardSnapshot("ward-12");
    render(<WardMap regions={snapshot.wardRegions} onSelectWard={() => undefined} />);

    fireEvent.click(screen.getByRole("button", { name: "Heat Intensity" }));

    expect(screen.getByRole("button", { name: "Heat Intensity" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("DEMONSTRATION HEAT INTENSITY")).toBeInTheDocument();
    expect(screen.getByText("Illustrative visualization · Not model output · Not authoritative GIS data")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Demo intensity" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ward 12, selectable region/ })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "Ward Severity" }));

    expect(screen.getByRole("button", { name: "Ward Severity" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("group", { name: "Demo severity" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ward 12, Very high/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("selects wards by mouse, Enter, and Space", () => {
    const onSelectWard = vi.fn();
    const snapshot = buildMockDashboardSnapshot("all");
    render(<WardMap regions={snapshot.wardRegions} onSelectWard={onSelectWard} />);
    const ward12 = screen.getByRole("button", { name: /Ward 12/ });
    const ward27 = screen.getByRole("button", { name: /Ward 27/ });
    const ward34 = screen.getByRole("button", { name: /Ward 34/ });

    fireEvent.click(ward12);
    fireEvent.keyDown(ward27, { key: "Enter" });
    fireEvent.keyDown(ward34, { key: " " });

    expect(onSelectWard).toHaveBeenNthCalledWith(1, "ward-12");
    expect(onSelectWard).toHaveBeenNthCalledWith(2, "ward-27");
    expect(onSelectWard).toHaveBeenNthCalledWith(3, "ward-34");
  });

  it("keeps keyboard ward selection active in heat intensity mode", () => {
    const onSelectWard = vi.fn();
    const snapshot = buildMockDashboardSnapshot("ward-12");
    render(<WardMap regions={snapshot.wardRegions} onSelectWard={onSelectWard} />);

    fireEvent.click(screen.getByRole("button", { name: "Heat Intensity" }));
    fireEvent.keyDown(screen.getByRole("button", { name: /Ward 27, selectable region/ }), {
      key: "Enter",
    });

    expect(onSelectWard).toHaveBeenCalledWith("ward-27");
  });

  it("announces an explicit unavailable state when no ward geometry is supplied", () => {
    render(<WardMap regions={[]} onSelectWard={() => undefined} />);

    expect(screen.getByRole("status")).toHaveTextContent("Ward geometry unavailable");
    expect(screen.queryByRole("button", { name: /Ward \d/ })).not.toBeInTheDocument();
  });
});
