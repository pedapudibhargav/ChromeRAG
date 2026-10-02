"""Learned block classifier: gradient-boosted trees evaluated with numpy only.

The model is trained offline (``poc/train_lbc.py``) on human-reviewed pages and stored as flat
arrays in ``assets/lbc_stage1.npz``. Prediction needs no machine-learning library.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_PATH = Path(__file__).resolve().parent / "assets" / "lbc_stage1.npz"


@dataclass
class TreeEnsemble:
    """Trees stored as one set of node arrays; ``roots[t]`` is the first node of tree ``t``."""

    feature: np.ndarray  # int32, -1 for a leaf
    threshold: np.ndarray  # float64
    left: np.ndarray  # int32, absolute node index
    right: np.ndarray  # int32
    value: np.ndarray  # float64, leaf value
    roots: np.ndarray  # int32
    baseline: float
    n_features: int
    max_depth: int

    def raw_score(self, X: np.ndarray) -> np.ndarray:
        """Sum of leaf values over all trees; every (row, tree) pair advances one level per step."""
        n = X.shape[0]
        rows = np.arange(n)[:, None]
        node = np.broadcast_to(self.roots[None, :], (n, len(self.roots))).copy()
        for _ in range(self.max_depth + 1):
            feat = self.feature[node]
            internal = feat >= 0
            if not internal.any():
                break
            go_left = X[rows, np.where(internal, feat, 0)] <= self.threshold[node]
            node = np.where(internal, np.where(go_left, self.left[node], self.right[node]), node)
        return self.baseline + self.value[node].sum(axis=1)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-self.raw_score(X)))

    def save(self, path: Path = MODEL_PATH) -> None:
        np.savez_compressed(
            path,
            feature=self.feature, threshold=self.threshold, left=self.left, right=self.right,
            value=self.value, roots=self.roots,
            meta=np.array([self.baseline, self.n_features, self.max_depth], dtype=np.float64),
        )

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> TreeEnsemble:
        z = np.load(path)
        meta = z["meta"]
        return cls(
            feature=z["feature"], threshold=z["threshold"], left=z["left"], right=z["right"],
            value=z["value"], roots=z["roots"], baseline=float(meta[0]), n_features=int(meta[1]),
            max_depth=int(meta[2]),
        )




STACK_NAMES = (
    "p", "p_prev", "p_next", "p_prev2", "p_next2", "box_mean_p", "box_min_p", "box_max_p", "box_n",
    "page_mean_p", "p_rank", "box_mean_p_prev_box", "box_mean_p_next_box",
)


def stack_features(p: np.ndarray, chars: np.ndarray, box: np.ndarray) -> np.ndarray:
    """Context columns built from first-stage probabilities ``p`` of one page.

    A block's label is correlated with its neighbours and with the other blocks in its box
    (a comment thread is noise from the first to the last block), so the second stage sees them.
    """
    n = len(p)
    out = np.zeros((n, len(STACK_NAMES)), dtype=np.float64)
    if n == 0:
        return out
    w = np.maximum(chars.astype(np.float64), 1.0)

    def shifted(k: int) -> np.ndarray:
        s = np.full(n, 0.5)
        if k > 0:
            s[k:] = p[:-k] if k < n else s[k:]
        else:
            s[:k] = p[-k:] if -k < n else s[:k]
        return s

    out[:, 0] = p
    out[:, 1], out[:, 2], out[:, 3], out[:, 4] = shifted(1), shifted(-1), shifted(2), shifted(-2)
    page_mean = float((p * w).sum() / w.sum())
    out[:, 9] = page_mean
    out[:, 10] = (np.argsort(np.argsort(p)) + 0.5) / n
    box_stat: dict[int, tuple[float, float, float, int]] = {}
    for b in np.unique(box):
        m = box == b
        if b < 0:
            continue
        pw = p[m]
        box_stat[int(b)] = (float((pw * w[m]).sum() / w[m].sum()), float(pw.min()), float(pw.max()), int(m.sum()))
    for i in range(n):
        st = box_stat.get(int(box[i]))
        if st is None:
            out[i, 5], out[i, 6], out[i, 7], out[i, 8] = p[i], p[i], p[i], 1
        else:
            out[i, 5], out[i, 6], out[i, 7], out[i, 8] = st
    prev_box = np.full(n, 0.5)
    next_box = np.full(n, 0.5)
    for i in range(1, n):
        prev_box[i] = out[i - 1, 5] if box[i] != box[i - 1] else prev_box[i - 1]
    for i in range(n - 2, -1, -1):
        next_box[i] = out[i + 1, 5] if box[i] != box[i + 1] else next_box[i + 1]
    out[:, 11], out[:, 12] = prev_box, next_box
    return out


@dataclass
class TwoStageModel:
    first: TreeEnsemble
    second: TreeEnsemble | None = None

    def predict(self, X: np.ndarray, chars: np.ndarray, box: np.ndarray) -> np.ndarray:
        p1 = self.first.predict_proba(X)
        if self.second is None:
            return p1
        X2 = np.hstack([X, stack_features(p1, chars, box)])
        return self.second.predict_proba(X2)

    def save(self, directory: Path) -> None:
        self.first.save(directory / "lbc_stage1.npz")
        stale = directory / "lbc_stage2.npz"
        if self.second is not None:
            self.second.save(stale)
        elif stale.exists():
            stale.unlink()

    @classmethod
    def load(cls, directory: Path = MODEL_PATH.parent) -> TwoStageModel | None:
        first = directory / "lbc_stage1.npz"
        if not first.is_file():
            return None
        second = directory / "lbc_stage2.npz"
        return cls(TreeEnsemble.load(first), TreeEnsemble.load(second) if second.is_file() else None)


@lru_cache(maxsize=1)
def default_two_stage() -> TwoStageModel | None:
    return TwoStageModel.load()
