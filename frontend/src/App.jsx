import React, { useEffect, useState } from "react";
import MapView from "./components/MapView.jsx";
import RouteControls from "./components/RouteControls.jsx";
import { fetchHealth, fetchRoutes, fetchRisk } from "./api.js";

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
    try {
      const data = await fetchRoutes({ origin, destination, alpha, hour });
      setRoutes(data.routes);
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
