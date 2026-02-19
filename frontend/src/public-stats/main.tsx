import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import PublicStatsApp from "@/public-stats/app";
import "@/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PublicStatsApp />
  </StrictMode>,
);
