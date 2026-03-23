import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { App } from "./router/App";
import { applyThemeParams } from "../src/telegram/tma";
import { setInitData } from "./api/http";
import "./index.css";

const qc = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);

(async () => {
  let tma = (window as any).Telegram?.WebApp;
  if (!tma) {
    await new Promise((resolve) => {
      const interval = setInterval(() => {
        if ((window as any).Telegram?.WebApp) {
          clearInterval(interval);
          resolve((window as any).Telegram.WebApp);
        }
      }, 50);
      setTimeout(() => {
        clearInterval(interval);
        resolve(null);
      }, 2000);
    });
    tma = (window as any).Telegram?.WebApp;
  }
  console.log("tma:", tma);
  const initData = tma?.initData || "";
  console.log("initData:", initData);
  if (initData) setInitData(initData);
  if (tma?.themeParams) applyThemeParams(tma.themeParams);
})();