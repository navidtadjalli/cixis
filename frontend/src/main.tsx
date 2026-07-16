import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { RevenueProvider } from "./context/RevenueContext";
import "./index.css";
// Brand accent overrides — generated per BRAND, must load after index.css so its
// :root vars win. See scripts/gen-brand.mjs.
import "./brand.generated.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RevenueProvider>
      <App />
    </RevenueProvider>
  </React.StrictMode>,
);
