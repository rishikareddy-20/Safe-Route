// Thin API client. In dev, Vite proxies /api -> http://localhost:8000 (see vite.config.js).
const BASE = import.meta.env.VITE_API_BASE || "/api";

export async function fetchHealth() {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error(`health ${res.status}`);
  return res.json();
}

export async function fetchRoutes({ origin, destination, alpha, hour }) {
  const res = await fetch(`${BASE}/route`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origin, destination, alpha, hour }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `route ${res.status}`);
  }
  return res.json();
}

export async function fetchRisk(hour, bbox) {
  const params = new URLSearchParams({ hour: String(hour) });
  if (bbox) {
    params.set("min_lng", bbox[0]);
    params.set("min_lat", bbox[1]);
    params.set("max_lng", bbox[2]);
    params.set("max_lat", bbox[3]);
  }
  const res = await fetch(`${BASE}/segment-risk?${params}`);
  if (!res.ok) throw new Error(`risk ${res.status}`);
  return res.json();
}
