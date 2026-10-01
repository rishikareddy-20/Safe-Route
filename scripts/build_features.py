"""Engineer per-segment features and the model training table.

What it does:
  1. Load the OSM graph edges as a GeoDataFrame (the segments).
  2. Attach crimes / crashes / light-outages to their nearest segment (within
     config.INCIDENT_BUFFER_M meters), working in a metric CRS.
  3. Split incidents in time: an earlier window builds features, a later window builds
     labels. This is a time-based split to avoid leakage.
  4. Write:
       segment_features.parquet  (static features + hourly histogram, per segment)
       train.parquet             (seg x hour rows with FEATURE_COLUMNS + label)
       edges.geojson             (segment geometries for the risk heatmap)

Run:  python -m scripts.build_features
"""
from __future__ import annotations

import json

from backend.app import config
from backend.app.feature_schema import (
    FEATURE_COLUMNS,
    HIST_COLUMNS,
    STATIC_MODEL_COLUMNS,
    make_feature_frame,
)

# Ordinal encoding of OSM highway class (bigger road -> higher number).
ROAD_CLASS = {
    "residential": 1,
    "living_street": 1,
    "unclassified": 1,
    "tertiary": 2,
    "tertiary_link": 2,
    "secondary": 3,
    "secondary_link": 3,
    "primary": 4,
    "primary_link": 4,
    "trunk": 5,
    "trunk_link": 5,
    "motorway": 6,
    "motorway_link": 6,
}
GRID_DEG = 0.01  # ~1 km cells for area-level crime normalization


def _road_class(highway) -> int:
    if isinstance(highway, list):
        highway = highway[0] if highway else "residential"
    return ROAD_CLASS.get(str(highway), 1)


def _load_points(path, lat_col="latitude", lng_col="longitude", date_col=None):
    """Load a raw CSV into a GeoDataFrame of points (WGS84). None if the file is absent."""
    import geopandas as gpd
    import pandas as pd

    if not path.exists():
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lng_col] = pd.to_numeric(df[lng_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lng_col])
    if date_col and date_col in df.columns:
        df["_ts"] = pd.to_datetime(df[date_col], errors="coerce")
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df[lng_col], df[lat_col]), crs=config.WGS84
    )
    return gdf


def _attach_nearest_seg(points_gdf, edges_m):
    """Attach the nearest seg_id to each point within the buffer (metric-CRS join)."""
    import geopandas as gpd

    pts_m = points_gdf.to_crs(config.METRIC_CRS)
    joined = gpd.sjoin_nearest(
        pts_m,
        edges_m[["seg_id", "geometry"]],
        how="inner",
        max_distance=config.INCIDENT_BUFFER_M,
        distance_col="_dist",
    )
    return joined


def main() -> None:
    import numpy as np
    import osmnx as ox
    import pandas as pd

    if not config.GRAPH_PATH.exists():
        raise SystemExit("Graph missing. Run `python -m scripts.build_graph` first.")

    print("[features] loading graph edges ...")
    G = ox.load_graphml(config.GRAPH_PATH)
    edges = ox.graph_to_gdfs(G, nodes=False).reset_index()
    edges["seg_id"] = edges["seg_id"].astype(str)
    edges["length"] = pd.to_numeric(edges["length"], errors="coerce").fillna(0.0)
    edges["lit"] = pd.to_numeric(edges.get("lit", 0), errors="coerce").fillna(0).astype(int)
    edges["road_class"] = edges.get("highway", "residential").apply(_road_class)

    seg = edges[["seg_id", "length", "lit", "road_class", "geometry"]].copy()
    seg = seg.groupby("seg_id", as_index=False).agg(
        length=("length", "sum"),
        lit=("lit", "max"),
        road_class=("road_class", "max"),
        geometry=("geometry", "first"),
    )
    import geopandas as gpd

    seg = gpd.GeoDataFrame(seg, geometry="geometry", crs=edges.crs)
    edges_m = seg.to_crs(config.METRIC_CRS)

    # Crimes: split into a feature window and a later label window.
    print("[features] attaching crimes to segments ...")
    crimes = _load_points(config.CRIMES_RAW_PATH, date_col="date")
    if crimes is None:
        raise SystemExit("No crimes data. Run `python -m scripts.ingest_socrata` first.")

    crimes["severity"] = (
        crimes.get("primary_type", "")
        .astype(str).str.upper()
        .map(config.CRIME_SEVERITY)
        .fillna(config.DEFAULT_CRIME_SEVERITY)
    )
    crimes["hour"] = crimes["_ts"].dt.hour.fillna(0).astype(int)

    cj = _attach_nearest_seg(crimes, edges_m)
    # Time split: earlier 70% -> features, later 30% -> labels.
    cutoff = cj["_ts"].quantile(0.7)
    feat_c = cj[cj["_ts"] <= cutoff]
    label_c = cj[cj["_ts"] > cutoff]
    print(f"[features] crime split at {cutoff}: "
          f"{len(feat_c):,} feature rows / {len(label_c):,} label rows")

    # Static weighted count + hourly histogram from the feature window.
    wcount = feat_c.groupby("seg_id")["severity"].sum().rename("crime_wcount")
    hist = (
        feat_c.pivot_table(index="seg_id", columns="hour", values="severity",
                           aggfunc="sum", fill_value=0.0)
        .reindex(columns=range(24), fill_value=0.0)
    )
    hist.columns = HIST_COLUMNS

    # Crashes and light outages.
    print("[features] attaching crashes & light outages ...")
    crashes = _load_points(config.CRASHES_RAW_PATH, date_col="crash_date")
    if crashes is not None:
        aj = _attach_nearest_seg(crashes, edges_m)
        accidents = aj.groupby("seg_id").size().rename("accident_count")
    else:
        accidents = pd.Series(dtype="float64", name="accident_count")

    lights = _load_points(config.LIGHTS_RAW_PATH, date_col="creation_date")
    if lights is not None:
        lj = _attach_nearest_seg(lights, edges_m)
        light_out = lj.groupby("seg_id").size().rename("light_out_count")
    else:
        light_out = pd.Series(dtype="float64", name="light_out_count")

    # Assemble the static per-segment table.
    static = seg.set_index("seg_id")[["length", "lit", "road_class"]].copy()
    static = static.join([wcount, accidents, light_out]).join(hist)
    static = static.fillna(0.0)
    static["crime_density"] = static["crime_wcount"] / (static["length"] / 100.0 + 1.0)

    # Normalize crime against a ~1km grid to dampen reporting bias.
    seg_wgs = seg.to_crs(config.WGS84)
    cent = seg_wgs.geometry.centroid
    grid = (
        (cent.y / GRID_DEG).round().astype(int).astype(str)
        + "_"
        + (cent.x / GRID_DEG).round().astype(int).astype(str)
    )
    grid.index = seg["seg_id"].values
    static["_grid"] = grid.reindex(static.index).values
    cell_rate = static.groupby("_grid")["crime_wcount"].transform("mean")
    top = cell_rate.quantile(0.95) or 1.0
    static["area_crime_norm"] = (cell_rate / top).clip(0, 1)
    static = static.drop(columns=["_grid"])

    static = static.reset_index()  # seg_id back as a column
    keep = ["seg_id"] + STATIC_MODEL_COLUMNS + HIST_COLUMNS
    static_out = static[keep].copy()
    static_out.to_parquet(config.SEGMENT_FEATURES_PATH, index=False)
    print(f"[features] saved static features -> {config.SEGMENT_FEATURES_PATH} "
          f"({len(static_out):,} segments)")

    # edges.geojson for the heatmap layer.
    geo = seg_wgs[["seg_id", "geometry"]].copy()
    geo["geometry"] = geo.geometry.simplify(0.00005)
    geo.to_file(config.EDGES_GEOJSON_PATH, driver="GeoJSON")
    print(f"[features] saved edge geometries -> {config.EDGES_GEOJSON_PATH}")

    # Training table: seg x hour, labels from the label window.
    print("[features] building training table ...")
    label_counts = (
        label_c.groupby(["seg_id", "hour"])["severity"].sum()
        .rename("label").reset_index()
    )
    label_map = {(r.seg_id, int(r.hour)): float(r.label)
                 for r in label_counts.itertuples()}

    frames = []
    for hour in range(24):
        X, seg_ids = make_feature_frame(static_out, hour)
        X = X.copy()
        X["seg_id"] = seg_ids.values
        X["label"] = [label_map.get((s, hour), 0.0) for s in seg_ids.values]
        frames.append(X)
    train = pd.concat(frames, ignore_index=True)

    # Down-sample zero-label rows (keep all positives + 3x negatives).
    pos = train[train["label"] > 0]
    neg = train[train["label"] == 0]
    n_neg = min(len(neg), max(len(pos) * 3, 5000))
    neg = neg.sample(n=n_neg, random_state=42) if len(neg) > n_neg else neg
    train = pd.concat([pos, neg], ignore_index=True).sample(frac=1.0, random_state=42)

    train[["seg_id"] + FEATURE_COLUMNS + ["label"]].to_parquet(
        config.TRAIN_TABLE_PATH, index=False
    )
    print(f"[features] saved training table -> {config.TRAIN_TABLE_PATH} "
          f"({len(train):,} rows, {len(pos):,} positive)")

    # Small summary for reproducibility.
    summary = {
        "n_segments": int(len(static_out)),
        "n_train_rows": int(len(train)),
        "n_positive": int(len(pos)),
        "crime_feature_rows": int(len(feat_c)),
        "crime_label_rows": int(len(label_c)),
        "cutoff": str(cutoff),
    }
    (config.PROCESSED_DIR / "features_summary.json").write_text(json.dumps(summary, indent=2))
    print("Features complete.")


if __name__ == "__main__":
    main()
