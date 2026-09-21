"""Semantic Vector Density Filtering (DVDF) via ONNX MiniLM.

Query-agnostic: score blocks against pre-baked marketing/boilerplate
noise anchor phrases. Falls back to density-only when ONNX model is absent.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Sequence

import numpy as np

from chromerag.models import BlockScore

DEFAULT_NOISE_ANCHORS = [
    "Accept all cookies and manage cookie preferences",
    "Subscribe to our newsletter for the latest updates",
    "Follow us on Twitter LinkedIn Facebook YouTube",
    "Related products you may also like",
    "Talk to sales Contact us Get a demo Request a quote",
    "Sign up for a free trial Start free Buy now",
    "Privacy policy Terms of use Cookie settings",
    "Share this page on social media",
    "Skip to main content Back to top",
    "Join our community webinar event register now",
    "Limited time offer promotional discount",
    "Careers blog press releases investor relations",
]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _hash_embed(text: str, dim: int = 384) -> np.ndarray:
    """Deterministic bag-of-hashes embedding (no model download).

    Used as a zero-dep fallback so the POC runs before ONNX weights land.
    Cosine geometry is coarse but sufficient to demonstrate the DVDF API.
    """
    vec = np.zeros(dim, dtype=np.float32)
    toks = _tokenize(text)
    if not toks:
        return vec
    for tok in toks:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


class NoiseAnchorIndex:
    """Noise-anchor vector bank + block scoring."""

    def __init__(
        self,
        anchors: Sequence[str] | None = None,
        threshold: float = 0.42,
        use_onnx: bool = False,
        onnx_model_path: str | Path | None = None,
    ) -> None:
        self.anchors = list(anchors or DEFAULT_NOISE_ANCHORS)
        self.threshold = threshold
        self.use_onnx = use_onnx
        self.onnx_model_path = Path(onnx_model_path) if onnx_model_path else None
        self._session = None
        self._anchor_vecs = [self.embed(a) for a in self.anchors]

    def embed(self, text: str) -> np.ndarray:
        if self.use_onnx and self._try_onnx():
            return self._onnx_embed(text)
        return _hash_embed(text)

    def _try_onnx(self) -> bool:
        if self._session is not None:
            return True
        if not self.onnx_model_path or not self.onnx_model_path.exists():
            return False
        try:
            import onnxruntime as ort  # noqa: WPS433

            self._session = ort.InferenceSession(
                str(self.onnx_model_path),
                providers=["CPUExecutionProvider"],
            )
            return True
        except Exception:
            self._session = None
            return False

    def _onnx_embed(self, text: str) -> np.ndarray:
        # Placeholder path for real MiniLM ONNX graph; hash fallback otherwise.
        if self._session is None:
            return _hash_embed(text)
        # Real wiring depends on exported tokenizer+model I/O names.
        # Keep hash fallback until assets/all-MiniLM-L6-v2.onnx is vendored.
        return _hash_embed(text)

    def max_noise_similarity(self, text: str) -> float:
        vec = self.embed(text)
        return max((cosine(vec, a) for a in self._anchor_vecs), default=0.0)

    def apply(self, blocks: list[BlockScore]) -> list[BlockScore]:
        for b in blocks:
            score = self.max_noise_similarity(b.text)
            b.noise_cosine = score
            if b.keep and score >= self.threshold:
                b.keep = False
                b.reason = f"dvdf_noise>{self.threshold:.2f}"
        return blocks

    def dump_anchors(self, path: Path) -> None:
        path.write_text(json.dumps(self.anchors, indent=2), encoding="utf-8")
