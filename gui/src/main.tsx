// SPDX-License-Identifier: AGPL-3.0-or-later
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { initToken } from "./api";
import "./app.css";

initToken();
const root = document.getElementById("root");
if (root) createRoot(root).render(<StrictMode><App /></StrictMode>);
