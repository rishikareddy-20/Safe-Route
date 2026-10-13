"""Evaluate the trained system and print report-ready metrics.

Two kinds of numbers:

  1. Model ranking quality (does the risk model order streets correctly?)
       ROC-AUC and average precision on a held-out split, plus top-decile lift: how
       concentrated real incidents are in the segments the model flags as riskiest.

  2. Route-level trade-off (does safety-aware routing actually help?)
       Over many random origin/destination pairs, how much lower the risk of the safest
       route is vs the fastest, and how much extra travel time that costs.

Everything is computed from your trained artifacts and written to models/evaluation.json.

Run (after training):  python -m scripts.evaluate
"""
from __future__ import annotations

import json
import random

from backend.app import config
from backend.app.feature_schema import FEATURE_COLUMNS


def evaluate_model_ranking() -> dict:
    """Ranking metrics on the same held-out split train_model.py used."""
    import lightgbm as lgb
    import numpy as np
    import pandas as pd
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.model_selection import train_test_split

    if not (config.TRAIN_TABLE_PATH.exists() and config.MODEL_PATH.exists()):
        print("[model] train table or model missing - run the pipeline first.")
        return {}

    df = pd.read_parquet(config.TRAIN_TABLE_PATH)
    X = df[FEATURE_COLUMNS]
    y = df["label"].astype("float64")
    # Same split as training (test_size=0.2, random_state=42) -> same validation rows.
    _, X_val, _, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    booster = lgb.Booster(model_file=str(config.MODEL_PATH))
    pred = booster.predict(X_val)

    y_bin = (y_val.to_numpy() > 0).astype(int)
    out: dict = {"n_val_rows": int(len(y_val)), "positive_rate": float(y_bin.mean())}

    if y_bin.sum() == 0 or y_bin.sum() == len(y_bin):
        print("[model] validation set has only one class - skipping ranking metrics.")
        return out

    out["roc_auc"] = float(roc_auc_score(y_bin, pred))
    out["average_precision"] = float(average_precision_score(y_bin, pred))

    # Top-decile lift: of all incidents, what share falls in the 10% of segment-hours
    # the model ranks riskiest? Lift = that share / 0.10 (1.0 = no better than random).
    order = np.argsort(-pred)
    top_n = max(1, int(0.10 * len(pred)))
    captured = y_bin[order[:top_n]].sum() / y_bin.sum()
    out["top_decile_capture"] = float(captured)       # e.g. 0.42 = 42% of incidents
    out["top_decile_lift"] = float(captured / 0.10)   # e.g. 4.2x random

    print("\n=== MODEL RANKING QUALITY ===")
    print(f"  ROC-AUC                : {out['roc_auc']:.3f}")
    print(f"  Average precision      : {out['average_precision']:.3f}")
    print(f"  Top-10% capture        : {out['top_decile_capture']*100:.1f}% of incidents")
    print(f"  Top-decile lift        : {out['top_decile_lift']:.1f}x vs random")
    return out


def evaluate_routing(n_pairs: int = 200, hour: int = 22, min_len_m: float = 1000.0) -> dict:
    """Compare safest vs fastest routes over many random origin/destination pairs."""
    import numpy as np

    from backend.app.graph_loader import GraphContext
    from backend.app.routing import Router
    from backend.app.scoring import SegmentScorer

    graph = GraphContext()
    scorer = SegmentScorer()
    if not (graph.load() and scorer.load()):
        print("[routing] graph or features missing - run the pipeline first.")
        return {}
    router = Router(graph, scorer)

    nodes = list(graph.G.nodes())
    rng = random.Random(42)

    risk_reductions = []   # % lower risk of safest vs fastest
    time_penalties = []    # % extra travel time of safest vs fastest
    helped = 0
    evaluated = 0
    attempts = 0

    while evaluated < n_pairs and attempts < n_pairs * 20:
        attempts += 1
        a, b = rng.choice(nodes), rng.choice(nodes)
        if a == b:
            continue
        o = graph.node_latlng(a)
        d = graph.node_latlng(b)
        try:
            routes = {r["label"]: r for r in router.route(o, d, alpha=0.5, hour=hour)}
        except Exception:
            continue
        if "fastest" not in routes or "safest" not in routes:
            continue
        fast, safe = routes["fastest"], routes["safest"]
        if fast["distance_m"] < min_len_m:
            continue

        evaluated += 1
        rf, rs = fast["mean_risk"], safe["mean_risk"]
        tf, ts = fast["travel_time_s"], safe["travel_time_s"]
        if rf > 0:
            risk_reductions.append((rf - rs) / rf * 100.0)
        if tf > 0:
            time_penalties.append((ts - tf) / tf * 100.0)
        if rs < rf:
            helped += 1

    out = {
        "hour": hour,
        "pairs_evaluated": evaluated,
        "mean_risk_reduction_pct": float(np.mean(risk_reductions)) if risk_reductions else 0.0,
        "median_risk_reduction_pct": float(np.median(risk_reductions)) if risk_reductions else 0.0,
        "mean_time_penalty_pct": float(np.mean(time_penalties)) if time_penalties else 0.0,
        "median_time_penalty_pct": float(np.median(time_penalties)) if time_penalties else 0.0,
        "share_safer_route_found_pct": float(helped / evaluated * 100.0) if evaluated else 0.0,
    }

    print("\n=== ROUTE-LEVEL TRADE-OFF (safest vs fastest) ===")
    print(f"  Pairs evaluated        : {out['pairs_evaluated']} (hour {hour}:00)")
    print(f"  Mean risk reduction    : {out['mean_risk_reduction_pct']:.1f}%")
    print(f"  Median risk reduction  : {out['median_risk_reduction_pct']:.1f}%")
    print(f"  Mean extra travel time : {out['mean_time_penalty_pct']:.1f}%")
    print(f"  A safer route existed  : {out['share_safer_route_found_pct']:.0f}% of trips")
    return out


def main() -> None:
    model_metrics = evaluate_model_ranking()
    routing_metrics = evaluate_routing()

    report = {"model": model_metrics, "routing": routing_metrics}
    out_path = config.MODELS_DIR / "evaluation.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
