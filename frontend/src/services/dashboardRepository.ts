import type { DashboardSnapshot } from "../types/dashboard";

export interface DashboardRepository {
  getSnapshot(wardId: string): Promise<DashboardSnapshot>;
}
