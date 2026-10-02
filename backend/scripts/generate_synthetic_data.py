"""Generate the synthetic POC dataset (roads, pole sites, footfall model output).

Usage (from ``backend/``):
    python -m scripts.generate_synthetic_data
    python -m scripts.generate_synthetic_data --seed 7 --out data/generated

Output is deterministic for a given seed. The footfall file simulates the
batch output of an upstream footfall model; GeoBid reads it through
``SyntheticFootfallProvider``.
"""

import argparse
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.synthetic.generator import generate_dataset, write_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=settings.synthetic_seed)
    parser.add_argument("--out", type=Path, default=settings.synthetic_data_dir)
    parser.add_argument("--spacing-km", type=float, default=1.0, help="approx. distance between poles")
    args = parser.parse_args()

    ds = generate_dataset(seed=args.seed, spacing_km=args.spacing_km)
    write_dataset(ds, args.out)

    footfalls = sorted((r.footfall for r in ds.footfall), reverse=True)
    print(f"Synthetic dataset written to {args.out.resolve()}")
    print(f"  roads: {len(ds.roads)}   poles: {len(ds.poles)}   seed: {args.seed}")
    print(f"  footfall range: {footfalls[-1]:,} – {footfalls[0]:,}")
    for road, n in Counter(p.road for p in ds.poles).most_common():
        print(f"  {n:>3}  {road}")


if __name__ == "__main__":
    main()
