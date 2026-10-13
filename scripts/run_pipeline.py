"""Run the full offline pipeline end to end.

    python -m scripts.run_pipeline

Runs ingest -> build_graph -> build_features -> train_model in order. Each stage is also
runnable on its own (see SETUP.md) if you want to inspect intermediate output.
"""
from __future__ import annotations

import time


def main() -> None:
    from scripts import build_features, build_graph, ingest_socrata, train_model

    stages = [
        ("Ingest Chicago open data", ingest_socrata.main),
        ("Build OSM street graph", build_graph.main),
        ("Engineer features", build_features.main),
        ("Train risk model", train_model.main),
    ]
    for i, (name, fn) in enumerate(stages, 1):
        print("\n" + "=" * 70)
        print(f"STAGE {i}/{len(stages)}: {name}")
        print("=" * 70)
        t0 = time.time()
        fn()
        print(f"-> done in {time.time() - t0:.1f}s")

    print("\nPipeline complete. Start the API with:")
    print("    uvicorn backend.app.main:app --reload")


if __name__ == "__main__":
    main()
