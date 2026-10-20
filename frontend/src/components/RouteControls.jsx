import React from "react";

export const ROUTE_COLORS = {
  fastest: "#e53935", // red
  safest: "#2e7d32", // green
  balanced: "#1e88e5", // blue
};

const HOURS = Array.from({ length: 24 }, (_, h) => h);

function fmtDist(m) {
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`;
}
function fmtTime(s) {
  const min = Math.round(s / 60);
  return min >= 60 ? `${Math.floor(min / 60)}h ${min % 60}m` : `${min} min`;
}

export default function RouteControls({
  alpha,
  setAlpha,
  hour,
  setHour,
  onFind,
  onClear,
  showRisk,
  onToggleRisk,
  loading,
  routes,
}) {
  return (
    <div className="controls">
      <label className="field">
        <span className="field-label">
          Priority: <strong>{alpha <= 0.34 ? "Safety" : alpha >= 0.66 ? "Speed" : "Balanced"}</strong>
        </span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={alpha}
          onChange={(e) => setAlpha(parseFloat(e.target.value))}
        />
        <div className="range-ends">
          <span>Safest</span>
          <span>Fastest</span>
        </div>
      </label>

      <label className="field">
        <span className="field-label">Time of day</span>
        <select value={hour} onChange={(e) => setHour(parseInt(e.target.value, 10))}>
          {HOURS.map((h) => (
            <option key={h} value={h}>
              {String(h).padStart(2, "0")}:00
              {h >= 20 || h < 6 ? " · night" : ""}
            </option>
          ))}
        </select>
      </label>

      <div className="buttons">
        <button className="primary" onClick={onFind} disabled={loading}>
          {loading ? "Routing…" : "Find routes"}
        </button>
        <button onClick={onClear}>Clear</button>
      </div>

      <label className="checkbox">
        <input type="checkbox" checked={showRisk} onChange={onToggleRisk} />
        Show risk heatmap
      </label>

      {routes.length > 0 && (
        <div className="results">
          <h3>Routes</h3>
          {routes.map((r) => (
            <div className="route-card" key={r.label}>
              <span className="swatch" style={{ background: ROUTE_COLORS[r.label] }} />
              <div className="route-body">
                <div className="route-title">{r.label}</div>
                <div className="route-meta">
                  {fmtDist(r.distance_m)} · {fmtTime(r.travel_time_s)} · risk{" "}
                  <strong>{(r.mean_risk * 100).toFixed(0)}%</strong>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
