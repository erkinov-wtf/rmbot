import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AppToaster } from "@/components/ui/app-toaster";
import MiniApp from "@/miniapp/app";
import { I18nProvider } from "@/i18n";
import "@/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider persistLanguagePreference={false}>
      <MiniApp />
      <AppToaster />
    </I18nProvider>
  </StrictMode>,
);
