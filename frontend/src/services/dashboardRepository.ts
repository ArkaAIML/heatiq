import type { DashboardSnapshot, WardOption } from "../types/dashboard";

/**
 * Presentation boundary for dashboard data.
 *
 * A future backend adapter should implement this interface and translate an
 * approved API contract into DashboardSnapshot. UI components must not depend
 * on endpoint paths, transport payloads, or fetch calls directly.
 */
export interface DashboardRepository {
  readonly wardOptions: readonly WardOption[];
  getSnapshot(wardId: string): Promise<DashboardSnapshot>;
  refresh?(): void;
}
