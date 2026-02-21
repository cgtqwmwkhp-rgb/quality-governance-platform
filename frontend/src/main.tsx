import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { ThemeProvider } from "./contexts/ThemeContext";
import { TooltipProvider } from "./components/ui/Tooltip";
import { initWebVitals } from "./utils/web-vitals";
import { errorReporting } from "./services/errorReporting";
import "./index.css";

if (import.meta.env.DEV) {
  import("@axe-core/react").then((axe) => {
    axe.default(React, ReactDOM, 1000);
  });
}

// Build version stamp for deployment verification
const BUILD_SHA = import.meta.env["VITE_BUILD_SHA"] || "dev";
const BUILD_TIME =
  import.meta.env["VITE_BUILD_TIME"] || new Date().toISOString();

// Expose for debugging (no secrets)
(window as unknown as Record<string, string>)["__BUILD_SHA__"] = BUILD_SHA;
(window as unknown as Record<string, string>)["__BUILD_TIME__"] = BUILD_TIME;

// Log once on startup for deployment verification
console.log(`[QGP] Build: ${BUILD_SHA} @ ${BUILD_TIME}`);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <TooltipProvider>
        <App />
      </TooltipProvider>
    </ThemeProvider>
  </React.StrictMode>,
);

initWebVitals();
errorReporting.init();
