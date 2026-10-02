"""Train the two-stage block classifier and export it for numpy-only inference.

Needs scikit-learn (training only; the shipped package does not).
Stage 1 sees one block's own features. Stage 2 also sees stage-1 probabilities of the
neighbouring blocks and of the block's box (chromerag.lbc.stack_features), trained on
out-of-fold stage-1 probabilities so it never sees a probability the model fitted itself.

  python -m poc.train_lbc --data data/outputs/lbc/lbc_dev.npz --out-dir data/outputs/lbc/learn
  python -m poc.train_lbc --fit-all --out-dir src/chromerag/assets
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from chromerag.lbc import TreeEnsemble, TwoStageModel, stack_features


def export(clf) -> TreeEnsemble:
    feature, threshold, left, right, value, roots = [], [], [], [], [], []
    offset = 0
    depth = 0
    for stage in clf._predictors:
        nodes = stage[0].nodes
        roots.append(offset)
        for node in nodes:
            leaf = bool(node["is_leaf"])
            feature.append(-1 if leaf else int(node["feature_idx"]))
            threshold.append(float(node["num_threshold"]))
            left.append(offset + int(node["left"]))
            right.append(offset + int(node["right"]))
            value.append(float(node["value"]) if leaf else 0.0)
            depth = max(depth, int(node["depth"]))
        offset += len(nodes)
    return TreeEnsemble(
        feature=np.array(feature, dtype=np.int32), threshold=np.array(threshold, dtype=np.float64),
        left=np.array(left, dtype=np.int32), right=np.array(right, dtype=np.int32),
        value=np.array(value, dtype=np.float64), roots=np.array(roots, dtype=np.int32),
        baseline=float(np.asarray(clf._baseline_prediction).ravel()[0]),
        n_features=int(clf.n_features_in_), max_depth=depth,
    )


def page_slices(page: np.ndarray):
    starts = np.flatnonzero(np.r_[True, page[1:] != page[:-1]])
    ends = np.r_[starts[1:], len(page)]
    return list(zip(starts, ends, strict=True))


def stacked(p: np.ndarray, chars: np.ndarray, box: np.ndarray, page: np.ndarray) -> np.ndarray:
    out = np.zeros((len(p), 13), dtype=np.float64)
    for a, b in page_slices(page):
        out[a:b] = stack_features(p[a:b], chars[a:b], box[a:b])
    return out


def main() -> None:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/outputs/lbc/lbc_dev.npz")
    ap.add_argument("--iters", type=int, default=300)
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--lr", type=float, default=0.06)
    ap.add_argument("--fit-all", action="store_true", help="train on every page instead of the learn half")
    ap.add_argument("--holdout-fold", type=int, default=None, help="train on the other 4 site folds, validate on this one")
    ap.add_argument("--stack", action="store_true", help="also train the context (second) stage")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    z = np.load(a.data)
    X, y, w = z["X"].astype(np.float64), z["y"], z["w"]
    chars, box, page, fold, half = z["chars"], z["box"], z["page"], z["fold"], z["half"]
    train = np.ones(len(y), bool) if a.fit_all else half == 0
    valid = half == 1
    if a.holdout_fold is not None:
        train, valid = fold != a.holdout_fold, fold == a.holdout_fold

    def make():
        return HistGradientBoostingClassifier(
            max_iter=a.iters, max_depth=a.depth, learning_rate=a.lr, l2_regularization=1.0,
            min_samples_leaf=40, random_state=0)

    idx = np.flatnonzero(train)
    oof = np.zeros(len(y))
    for k in range(5 if a.stack else 0):
        fit = idx[fold[idx] != k]
        hold = idx[fold[idx] == k]
        oof[hold] = make().fit(X[fit], y[fit], sample_weight=w[fit]).predict_proba(X[hold])[:, 1]
    first = make().fit(X[idx], y[idx], sample_weight=w[idx])
    second = None
    if a.stack:
        X2 = np.hstack([X, stacked(oof, chars, box, page)])
        second = make().fit(X2[idx], y[idx], sample_weight=w[idx])
    model = TwoStageModel(export(first), export(second) if a.stack else None)

    # numpy copy must equal sklearn
    p1 = first.predict_proba(X[:3000])[:, 1]
    assert np.abs(model.first.predict_proba(X[:3000]) - p1).max() < 1e-9

    if not a.fit_all:
        vi = np.flatnonzero(valid)
        p1v = model.first.predict_proba(X[vi])
        runs = [("stage1", p1v)]
        if a.stack:
            p2 = model.second.predict_proba(np.hstack([X[vi], stacked(p1v, chars[vi], box[vi], page[vi])]))
            runs.append(("stage2", p2))
        for name, p in runs:
            print(name, "valid AUC", round(roc_auc_score(y[vi], p, sample_weight=w[vi]), 4))
            for thr in (0.35, 0.45, 0.55):
                pred = p >= thr
                tp = (w[vi] * (pred & (y[vi] == 1))).sum()
                print(f"   thr {thr}: word precision {tp / max(1, (w[vi] * pred).sum()):.3f} "
                      f"recall {tp / max(1, (w[vi] * (y[vi] == 1)).sum()):.3f}")
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    model.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
