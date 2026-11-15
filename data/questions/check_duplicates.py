#!/usr/bin/env python3
"""Flag near-duplicate questions (HW1 Step 4).

Embeds every question in questions_dev.jsonl + questions_test.jsonl with
sentence-transformers/all-MiniLM-L6-v2 and prints every pair whose cosine
similarity is >= --threshold (default 0.85, as in the HW1 spec). Exits with
status 1 if any pair is flagged, so it can be used as a check.

Usage:
    python data/questions/check_duplicates.py [--threshold 0.85] [--top 10]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

QUESTIONS_DIR = Path(__file__).resolve().parent
MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.85)
    ap.add_argument("--top", type=int, default=10, help="also print the N most similar pairs")
    args = ap.parse_args()

    # Plain HTTPS downloads work behind restrictive proxies; Xet transfer may not.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    from sentence_transformers import SentenceTransformer, util

    rows = []
    for name in ("questions_dev.jsonl", "questions_test.jsonl"):
        with open(QUESTIONS_DIR / name, encoding="utf-8") as f:
            rows += [json.loads(line) for line in f]

    model = SentenceTransformer(MODEL)
    emb = model.encode([r["question"] for r in rows], convert_to_tensor=True, normalize_embeddings=True)
    sim = util.cos_sim(emb, emb)

    pairs = sorted(((float(sim[i][j]), i, j) for i in range(len(rows)) for j in range(i + 1, len(rows))),
                   reverse=True)
    print(f"{len(rows)} questions, {len(pairs)} pairs; most similar:")
    for s, i, j in pairs[: args.top]:
        print(f"  {s:.3f}  {rows[i]['id']}: {rows[i]['question']}\n         {rows[j]['id']}: {rows[j]['question']}")

    flagged = [p for p in pairs if p[0] >= args.threshold]
    if flagged:
        print(f"\n{len(flagged)} pair(s) at or above {args.threshold}: rewrite one question in each.")
        sys.exit(1)
    print(f"\nNo pairs at or above {args.threshold}.")


if __name__ == "__main__":
    main()
