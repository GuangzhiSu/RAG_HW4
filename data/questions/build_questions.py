#!/usr/bin/env python3
"""Turn data/questions/questions_draft.json into the HW1 task-corpus schema and split it.

The schema follows the HW1 spec (docs: hw1_spec.md, hw4_spec.md):

  * context_index is 1-indexed: context[context_index[i] - 1] contains
    answers.text[i] at answers.answer_start[i]. (HW1: "You may treat it like a
    1-indexed list", and its example uses [1].)
  * multi-hop questions list every hop's context in "context"/"title", and
    context_index points only at the context with the final answer.
  * unanswerable questions have answers.text = [""], answer_start = [-1] and
    context = the near-miss passage that makes the question look answerable;
    their context_index is [1] (the spec leaves it unspecified).

For every question, each evidence entry names a corpus document (title) and an
anchor phrase. The gold context is the paragraph (line) of that document that
contains the anchor. Each gold answer must appear verbatim in the context of
its title; answer_start is its character offset in that context (the
occurrence nearest the anchor, if it appears more than once) and
context_index is the position of that context in the list.

Checks (the script exits with an error if any fails):
  * every evidence title exists in data/corpus/corpus.csv and its anchor is found
  * every answer appears verbatim in its context
  * answerable questions have >= 1 answer; unanswerable questions have none
    and at least one near-miss evidence title
  * ids are unique and types are valid

Output: data/questions/questions_dev.jsonl and questions_test.jsonl, a 50/50 split
stratified by type (fixed seed).

Usage:
    python data/questions/build_questions.py
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

QUESTIONS_DIR = Path(__file__).resolve().parent
CORPUS_CSV = QUESTIONS_DIR.parent / "corpus" / "corpus.csv"
INDEX_BASE = 1  # context_index is 1-indexed, as in the HW1 example
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
            idxs.append(hit[0] + INDEX_BASE)
            starts.append(hit[1])
            texts.append(ans["text"])

        if q["type"] == "unanswerable":
            if q["answers"]:
                errors.append(f"{qid}: unanswerable question has answers")
            if not titles:
                errors.append(f"{qid}: unanswerable question needs a near-miss title")
            starts, texts, idxs = [-1], [""], [INDEX_BASE]
        elif not texts:
            errors.append(f"{qid}: answerable question has no valid answer")
        if q["type"] == "multi_hop" and len(set(titles)) < 2:
            errors.append(f"{qid}: multi_hop question needs >= 2 articles")

        out.append({
            "answers": {"answer_start": starts, "text": texts, "context_index": idxs},
            "context": contexts,
            "id": qid,
            "question": q["question"],
            "title": titles,
            "type": q["type"],
        })

    for row in out:
        errors += validate_row(row)
    if errors:
        print("Validation failed:", *errors, sep="\n  ", file=sys.stderr)
        sys.exit(1)
    return out


def validate_row(r: dict) -> list[str]:
    """Independent check of one output row against the HW1 schema."""
    errs, qid = [], r.get("id")
    keys = {"answers", "context", "id", "question", "title", "type"}
    if set(r) != keys:
        return [f"{qid}: keys {sorted(r)} != {sorted(keys)}"]
    a = r["answers"]
    if set(a) != {"answer_start", "text", "context_index"}:
        return [f"{qid}: bad answers keys {sorted(a)}"]
    if not (len(a["answer_start"]) == len(a["text"]) == len(a["context_index"]) >= 1):
        errs.append(f"{qid}: answers lists differ in length or are empty")
    if len(r["context"]) != len(r["title"]) or not r["context"]:
        errs.append(f"{qid}: context and title lists differ in length or are empty")
    if not all(isinstance(x, str) and x for x in r["context"] + r["title"] + [r["question"], r["id"]]):
        errs.append(f"{qid}: empty or non-string field")
    for start, text, ci in zip(a["answer_start"], a["text"], a["context_index"]):
        if not (isinstance(start, int) and isinstance(ci, int)):
            errs.append(f"{qid}: answer_start/context_index must be ints")
            continue
        if not 1 <= ci <= len(r["context"]):
            errs.append(f"{qid}: context_index {ci} out of range")
            continue
        if r["type"] == "unanswerable":
            if (start, text) != (-1, ""):
                errs.append(f"{qid}: unanswerable must have text '' and answer_start -1")
        elif r["context"][ci - 1][start:start + len(text)] != text:
            errs.append(f"{qid}: context[{ci}][{start}:] does not start with {text!r}")
    return errs


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
    corpus = load_corpus(CORPUS_CSV)
    draft = json.loads((QUESTIONS_DIR / "questions_draft.json").read_text(encoding="utf-8"))
    rows = build(draft, corpus)
    dev, test = split(rows)
    write_jsonl(QUESTIONS_DIR / "questions_dev.jsonl", dev)
    write_jsonl(QUESTIONS_DIR / "questions_test.jsonl", test)
    for name, part in (("dev", dev), ("test", test)):
        counts = {t: sum(r["type"] == t for r in part) for t in TYPES}
        print(f"{name}: {len(part)} questions {counts}")


if __name__ == "__main__":
    main()
