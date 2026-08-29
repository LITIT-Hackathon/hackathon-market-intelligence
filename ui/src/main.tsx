import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { loadPayload } from "./data";
import "./styles.css";

const root = createRoot(document.getElementById("root")!);

loadPayload().then(
  (data) => root.render(<StrictMode><App data={data} /></StrictMode>),
  (err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err);
    root.render(
      <main style={{ padding: 32 }}>
        <p className="label">Opportunity Radar</p>
        <h2>No data</h2>
        <p className="lede">{msg}</p>
      </main>,
    );
  },
);
