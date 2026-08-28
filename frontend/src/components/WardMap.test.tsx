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
    expect(screen.getByRole("button", { name: /Ward 12, Very high/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Ward 27, Severe/ })).toHaveAttribute("aria-pressed", "false");
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
});
