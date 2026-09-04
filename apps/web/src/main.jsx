import React from "react";
import ReactDOM from "react-dom/client";
import App from "./app/App.jsx";
import "./app/index.css";
import { ErrorBoundary } from "./ErrorBoundary.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
