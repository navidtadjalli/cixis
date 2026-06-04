import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { RevenueProvider } from "./context/RevenueContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RevenueProvider>
      <App />
    </RevenueProvider>
  </React.StrictMode>,
);
