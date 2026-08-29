import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { apiDashboardRepository } from "./services/apiDashboardRepository";
import { mockDashboardRepository } from "./services/mockDashboardRepository";
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/dashboard.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App repository={import.meta.env.VITE_HEATIQ_DATA_MODE === "demo"
      ? mockDashboardRepository
      : apiDashboardRepository} />
  </StrictMode>,
);
