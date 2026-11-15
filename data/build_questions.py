#!/usr/bin/env python3
"""Turn data/questions_draft.json into the HW1 task-corpus schema and split it.

For every question, each evidence entry names a corpus document (title) and an
anchor phrase. The gold context is the paragraph (line) of that document that
contains the anchor. Each gold answer must appear verbatim in the context of
its title; answer_start is its character offset in that context (the
occurrence nearest the anchor, if it appears more than once) and
context_index is the position of that context in the list.

Checks (the script exits with an error if any fails):
  * every evidence title exists in data/corpus.csv and its anchor is found
  * every answer appears verbatim in its context
  * answerable questions have >= 1 answer; unanswerable questions have none
    and at least one near-miss evidence title
  * ids are unique and types are valid

Output: data/questions_dev.jsonl and data/questions_test.jsonl, a 50/50 split
stratified by type (fixed seed).

Usage:
    python data/build_questions.py
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
TYPES = ("factoid", "complex", "multi_hop", "unanswerable")
SEED = 697


def load_corpus(path: Path) -> dict[str, str]:
    csv.field_size_limit(sys.maxsize)
    with open(path, newline="", encoding="utf-8") as f:
        return {row["title"]: row["text"] for row in csv.DictReader(f)}


def find_paragraph(text: str, anchor: str) -> str | None:
    hits = [p for p in text.split("\n") if anchor in p]
    return hits[0] if hits else None


def occurrences_of(text: str, sub: str) -> list[int]:
    out, i = [], text.find(sub)
    while i != -1:
        out.append(i)
        i = text.find(sub, i + 1)
    return out


def build(draft: list[dict], corpus: dict[str, str]) -> list[dict]:
    errors, out, seen = [], [], set()
    for q in draft:
        qid = q["id"]
        if qid in seen:
            errors.append(f"{qid}: duplicate id")
        seen.add(qid)
        if q["type"] not in TYPES:
            errors.append(f"{qid}: bad type {q['type']!r}")

        contexts, titles, anchor_pos = [], [], []
        for ev in q["evidence"]:
            if ev["title"] not in corpus:
                errors.append(f"{qid}: title not in corpus: {ev['title']!r}")
                continue
            para = find_paragraph(corpus[ev["title"]], ev["anchor"])
            if para is None:
                errors.append(f"{qid}: anchor not found in {ev['title']!r}: {ev['anchor']!r}")
                continue
            contexts.append(para)
            titles.append(ev["title"])
            anchor_pos.append(para.find(ev["anchor"]))

        starts, texts, idxs = [], [], []
        for ans in q["answers"]:
            positions = [i for i, t in enumerate(titles) if t == ans["title"]]
            # every (context, offset) where the answer occurs; prefer the one
            # closest to that context's anchor, i.e. the supporting mention
            occurrences = [(i, j) for i in positions for j in occurrences_of(contexts[i], ans["text"])]
            hit = min(occurrences, key=lambda o: abs(o[1] - anchor_pos[o[0]]), default=None)
            if hit is None:
                errors.append(f"{qid}: answer {ans['text']!r} not verbatim in context of {ans['title']!r}")
                continue
            idxs.append(hit[0])
            starts.append(hit[1])
            texts.append(ans["text"])

        if q["type"] == "unanswerable":
            if q["answers"]:
                errors.append(f"{qid}: unanswerable question has answers")
            if not titles:
                errors.append(f"{qid}: unanswerable question needs a near-miss title")
        elif not texts:
            errors.append(f"{qid}: answerable question has no valid answer")

        out.append({
            "answers": {"answer_start": starts, "text": texts, "context_index": idxs},
            "context": contexts,
            "id": qid,
            "question": q["question"],
            "title": titles,
            "type": q["type"],
        })

    if errors:
        print("Validation failed:", *errors, sep="\n  ", file=sys.stderr)
        sys.exit(1)
    return out


def split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    by_type = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r)
    rng = random.Random(SEED)
    dev, test = [], []
    for t in TYPES:
        group = sorted(by_type[t], key=lambda r: r["id"])
        rng.shuffle(group)
        half = len(group) // 2
        dev += group[:half]
        test += group[half:]
    return sorted(dev, key=lambda r: r["id"]), sorted(test, key=lambda r: r["id"])


def write_jsonl(path: Path, rows: list[dict]):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    corpus = load_corpus(DATA_DIR / "corpus.csv")
    draft = json.loads((DATA_DIR / "questions_draft.json").read_text(encoding="utf-8"))
    rows = build(draft, corpus)
    dev, test = split(rows)
    write_jsonl(DATA_DIR / "questions_dev.jsonl", dev)
    write_jsonl(DATA_DIR / "questions_test.jsonl", test)
    for name, part in (("dev", dev), ("test", test)):
        counts = {t: sum(r["type"] == t for r in part) for t in TYPES}
        print(f"{name}: {len(part)} questions {counts}")


if __name__ == "__main__":
    main()
