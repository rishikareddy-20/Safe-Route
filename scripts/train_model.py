"""Train the LightGBM segment-risk model.

Target: severity-weighted incident intensity per segment-hour (from the label window).
The model is really used to rank segment-hours by risk, so we report regression error plus
a ranking metric (ROC-AUC of predictions vs "had an incident"), which is what matters for
choosing safer routes.

Saves:
  models/risk_model.txt   LightGBM booster
  models/model_meta.json  prediction min/max for [0,1] normalization at serving time
  models/metrics.json     evaluation metrics + feature importances

Run:  python -m scripts.train_model
"""
from __future__ import annotations

import json

from backend.app import config
from backend.app.feature_schema import FEATURE_COLUMNS


def main() -> None:
    import lightgbm as lgb
    import numpy as np
    import pandas as pd
    from sklearn.metrics import mean_squared_error, roc_auc_score
    from sklearn.model_selection import train_test_split

    if not config.TRAIN_TABLE_PATH.exists():
        raise SystemExit("Training table missing. Run `python -m scripts.build_features`.")

    df = pd.read_parquet(config.TRAIN_TABLE_PATH)
    X = df[FEATURE_COLUMNS]
    y = df["label"].astype("float64")

    X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    train_set = lgb.Dataset(X_tr, label=y_tr)
    val_set = lgb.Dataset(X_val, label=y_val, reference=train_set)

    params = {
        "objective": "regression",
        "metric": "rmse",
        "learning_rate": 0.05,
        "num_leaves": 63,
        "min_data_in_leaf": 50,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "verbose": -1,
    }

    print("[train] fitting LightGBM ...")
    booster = lgb.train(
        params,
        train_set,
        num_boost_round=600,
        valid_sets=[val_set],
        callbacks=[lgb.early_stopping(40), lgb.log_evaluation(50)],
    )

    val_pred = booster.predict(X_val)
    rmse = float(np.sqrt(mean_squared_error(y_val, val_pred)))
    # Ranking: can predictions separate "incident occurred" from "none"?
    y_bin = (y_val > 0).astype(int)
    auc = float(roc_auc_score(y_bin, val_pred)) if y_bin.nunique() > 1 else float("nan")

    # Serving normalization bounds (robust: 1st/99th percentile of predictions).
    all_pred = booster.predict(X)
    p_min = float(np.percentile(all_pred, 1))
    p_max = float(np.percentile(all_pred, 99))

    booster.save_model(str(config.MODEL_PATH))
    config.MODEL_META_PATH.write_text(json.dumps(
        {"pred_min": p_min, "pred_max": p_max, "features": FEATURE_COLUMNS}, indent=2))

    importances = dict(sorted(
        zip(FEATURE_COLUMNS, booster.feature_importance().tolist()),
        key=lambda kv: kv[1], reverse=True,
    ))
    metrics = {
        "rmse": rmse,
        "ranking_auc": auc,
        "n_rows": int(len(df)),
        "best_iteration": booster.best_iteration,
        "pred_min": p_min,
        "pred_max": p_max,
        "feature_importance": importances,
    }
    config.METRICS_PATH.write_text(json.dumps(metrics, indent=2))

    print(f"[train] RMSE={rmse:.4f}  ranking_AUC={auc:.3f}")
    print(f"[train] top features: {list(importances)[:5]}")
    print(f"[train] saved model -> {config.MODEL_PATH}")
    print("Training complete.")


if __name__ == "__main__":
    main()
