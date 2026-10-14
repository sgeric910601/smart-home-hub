import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { registerServiceWorker } from "./services/pwa";
import "./styles.css";
import "./responsive.css";
const client = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30000, refetchOnWindowFocus: false },
  },
});
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
if (import.meta.env.PROD) registerServiceWorker();
