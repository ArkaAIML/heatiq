import type { DashboardSnapshot, WardOption } from "../types/dashboard";

export interface DashboardRepository {
  readonly wardOptions: readonly WardOption[];
  getSnapshot(wardId: string): Promise<DashboardSnapshot>;
}
