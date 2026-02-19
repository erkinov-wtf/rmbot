import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import PublicStatsApp from "@/public-stats/app";
import { I18nProvider } from "@/i18n";
import "@/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <PublicStatsApp />
    </I18nProvider>
  </StrictMode>,
);
