"""Update strict_split_manifest.json after lbc_data / fit-all verify."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_split_manifest.json"
IDS = ROOT / "poc" / "wcxb_strict_train_ids.json"
LBC_NPZ = ROOT / "data" / "outputs" / "lbc" / "lbc_strict.npz"
ASSET = ROOT / "src" / "chromerag" / "assets" / "lbc_stage1.npz"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-npz", type=Path, required=True, help="fit-all output lbc_stage1.npz")
    ap.add_argument("--lbc-data", type=Path, default=LBC_NPZ)
    args = ap.parse_args()

    z = np.load(args.lbc_data)
    pages = len(z["ids"])
    blocks = len(z["y"])
    failed = sorted(set(json.loads(IDS.read_text(encoding="utf-8"))) - set(z["ids"].astype(str)))

    manifest: dict = {}
    if MANIFEST.is_file():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    manifest["lbc_feature_matrix_pages"] = int(pages)
    manifest["lbc_extraction_failed_ids"] = failed

    vp = args.verify_npz if args.verify_npz.is_absolute() else ROOT / args.verify_npz
    data = vp.read_bytes()
    manifest["shipped_lbc_stage1_npz"] = {
        "path": "src/chromerag/assets/lbc_stage1.npz",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "verified_against": str(vp.relative_to(ROOT)),
        "verified_match": ASSET.is_file() and ASSET.read_bytes() == data,
    }

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        "manifest updated pages",
        pages,
        "blocks",
        blocks,
        "failed",
        len(failed),
        "sha256",
        manifest["shipped_lbc_stage1_npz"]["sha256"][:16],
    )


if __name__ == "__main__":
    main()
