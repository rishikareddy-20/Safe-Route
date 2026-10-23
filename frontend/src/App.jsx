import React, { useEffect, useState } from "react";
import MapView from "./components/MapView.jsx";
import RouteControls from "./components/RouteControls.jsx";
import { fetchHealth, fetchRoutes, fetchRisk } from "./api.js";

// Great-circle distance in meters between two {lat,lng} points.
function distanceM(a, b) {
  const R = 6371000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

// How far a click can be from a routable street before we warn (meters).
const SNAP_WARN_M = 300;

export default function App() {
  const [origin, setOrigin] = useState(null); // {lat, lng}
  const [destination, setDestination] = useState(null);
  const [alpha, setAlpha] = useState(0.5);
  const [hour, setHour] = useState(18);
  const [routes, setRoutes] = useState([]);
  const [risk, setRisk] = useState(null);
  const [showRisk, setShowRisk] = useState(false);
  const [health, setHealth] = useState(null);
  const [status, setStatus] = useState("");
  const [snapNote, setSnapNote] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  // A map click sets origin, then destination, then starts over.
  function handleMapClick(latlng) {
    if (!origin || (origin && destination)) {
      setOrigin(latlng);
      setDestination(null);
      setRoutes([]);
      setStatus("Origin set. Click again for the destination.");
    } else {
      setDestination(latlng);
      setStatus("Destination set. Click Find routes.");
    }
  }

  async function findRoutes() {
    if (!origin || !destination) {
      setStatus("Pick an origin and a destination on the map first.");
      return;
    }
    setLoading(true);
    setStatus("");
    setSnapNote("");
    try {
      const data = await fetchRoutes({ origin, destination, alpha, hour });
      setRoutes(data.routes);

      // Warn if either click was far from the nearest routable Chicago street.
      const g = data.routes[0].geometry;
      const start = { lat: g[0][0], lng: g[0][1] };
      const end = { lat: g[g.length - 1][0], lng: g[g.length - 1][1] };
      const dStart = distanceM(origin, start);
      const dEnd = distanceM(destination, end);
      const far = [];
      if (dStart > SNAP_WARN_M) far.push(`start (~${(dStart / 1000).toFixed(1)} km)`);
      if (dEnd > SNAP_WARN_M) far.push(`end (~${(dEnd / 1000).toFixed(1)} km)`);
      if (far.length) {
        setSnapNote(
          `Your ${far.join(" and ")} ${
            far.length > 1 ? "aren't" : "isn't"
          } on a routable Chicago street, likely a suburb or off-road spot. ` +
            `The route uses the nearest point inside the city (pink dashed line).`
        );
      }
    } catch (err) {
      setStatus(`Error: ${err.message}`);
      setRoutes([]);
    } finally {
      setLoading(false);
    }
  }

  async function toggleRisk() {
    const next = !showRisk;
    setShowRisk(next);
    if (next && !risk) {
      try {
        const geo = await fetchRisk(hour);
        setRisk(geo);
      } catch (err) {
        setStatus(`Risk layer error: ${err.message}`);
      }
    }
  }

  // Refresh the risk layer when the hour changes while it is shown.
  useEffect(() => {
    if (showRisk) {
      fetchRisk(hour).then(setRisk).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hour]);

  function clearAll() {
    setOrigin(null);
    setDestination(null);
    setRoutes([]);
    setStatus("");
    setSnapNote("");
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Safe-Route</h1>
        <p className="subtitle">Chicago · safety-aware routing</p>

        <RouteControls
          alpha={alpha}
          setAlpha={setAlpha}
          hour={hour}
          setHour={setHour}
          onFind={findRoutes}
          onClear={clearAll}
          showRisk={showRisk}
          onToggleRisk={toggleRisk}
          loading={loading}
          routes={routes}
        />

        {status && <div className="status">{status}</div>}
        {snapNote && <div className="notice">⚠️ {snapNote}</div>}

        <div className="health">
          {health ? (
            <>
              <span className={`dot ${health.status === "ok" ? "ok" : "warn"}`} />
              {health.status === "ok"
                ? `Ready · ${health.n_edges?.toLocaleString()} segments · model: ${
                    health.model_loaded ? "trained" : "heuristic"
                  }`
                : "Backend not ready. Run the pipeline (see SETUP.md)"}
            </>
          ) : (
            <>
              <span className="dot warn" /> Backend unreachable (start uvicorn)
            </>
          )}
        </div>

        <p className="disclaimer">
          Risk figures are <strong>estimates</strong> from reported incident data, not
          safety guarantees. Reported crime reflects reporting/policing patterns. Use
          your own judgment.
        </p>
      </aside>

      <main className="map-pane">
        <MapView
          origin={origin}
          destination={destination}
          routes={routes}
          risk={showRisk ? risk : null}
          onMapClick={handleMapClick}
        />
      </main>
    </div>
  );
}
