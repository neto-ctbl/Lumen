import React from "react";
import ReactDOM from "react-dom/client";

import { LumenShell } from "./app/LumenShell";
import "./styles/tokens.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LumenShell />
  </React.StrictMode>,
);
