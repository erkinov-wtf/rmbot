import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import MiniApp from "@/miniapp/app";
import "@/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MiniApp />
  </StrictMode>,
);
