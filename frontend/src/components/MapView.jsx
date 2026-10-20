import React, { useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  GeoJSON,
  Tooltip,
  useMapEvents,
  useMap,
} from "react-leaflet";
import { ROUTE_COLORS } from "./RouteControls.jsx";

const CHICAGO = [41.8781, -87.6298];
// Approximate City of Chicago bounding box (SW corner, NE corner).
// The routing graph only covers the city, so keep the map inside it.
const CHICAGO_BOUNDS = [
  [41.644, -87.94], // south-west
  [42.023, -87.524], // north-east
];

// Risk 0..1 mapped to a green-yellow-red hue.
function riskColor(r) {
  const hue = (1 - Math.max(0, Math.min(1, r))) * 120; // 120=green, 0=red
  return `hsl(${hue}, 80%, 45%)`;
}

function ClickHandler({ onMapClick }) {
  useMapEvents({
    click(e) {
      onMapClick({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return null;
}

function FitBounds({ routes, origin, destination }) {
  const map = useMap();
  React.useEffect(() => {
    const pts = [];
    routes.forEach((r) => r.geometry.forEach((p) => pts.push(p)));
    if (origin) pts.push([origin.lat, origin.lng]);
    if (destination) pts.push([destination.lat, destination.lng]);
    if (pts.length >= 2) {
      map.fitBounds(pts, { padding: [40, 40] });
    }
  }, [routes, origin, destination, map]);
  return null;
}

export default function MapView({ origin, destination, routes, risk, onMapClick }) {
  const riskStyle = useMemo(
    () => (feature) => ({
      color: riskColor(feature.properties.risk),
      weight: 3,
      opacity: 0.7,
    }),
    []
  );

  // Draw fastest last so it sits on top; keep a stable order otherwise.
  const ordered = [...routes].sort((a, b) =>
    a.label === "fastest" ? 1 : b.label === "fastest" ? -1 : 0
  );

  return (
    <MapContainer
      center={CHICAGO}
      zoom={11}
      minZoom={11}
      maxBounds={CHICAGO_BOUNDS}
      maxBoundsViscosity={1.0}
      className="map"
    >
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickHandler onMapClick={onMapClick} />

      {risk && (
        <GeoJSON key={JSON.stringify(risk).length} data={risk} style={riskStyle} />
      )}

      {ordered.map((r) => (
        <Polyline
          key={r.label}
          positions={r.geometry}
          pathOptions={{
            color: ROUTE_COLORS[r.label] || "#555",
            weight: r.label === "fastest" ? 5 : 4,
            opacity: 0.9,
          }}
        >
          <Tooltip sticky>
            {r.label}: {(r.distance_m / 1000).toFixed(2)} km · risk{" "}
            {(r.mean_risk * 100).toFixed(0)}%
          </Tooltip>
        </Polyline>
      ))}

      {origin && (
        <CircleMarker
          center={[origin.lat, origin.lng]}
          radius={9}
          pathOptions={{ color: "#111", fillColor: "#4caf50", fillOpacity: 1 }}
        >
          <Tooltip permanent>Start</Tooltip>
        </CircleMarker>
      )}
      {destination && (
        <CircleMarker
          center={[destination.lat, destination.lng]}
          radius={9}
          pathOptions={{ color: "#111", fillColor: "#f44336", fillOpacity: 1 }}
        >
          <Tooltip permanent>End</Tooltip>
        </CircleMarker>
      )}

      <FitBounds routes={routes} origin={origin} destination={destination} />
    </MapContainer>
  );
}
