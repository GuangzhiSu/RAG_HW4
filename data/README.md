---
language:
- en
license: cc-by-sa-4.0
pretty_name: Anna Julia Cooper QA Corpus
size_categories:
- n<1K
task_categories:
- question-answering
configs:
- config_name: default
  data_files:
  - split: train
    path: corpus/corpus.csv
---

# Anna Julia Cooper QA Corpus

A retrieval corpus and question set about **Anna Julia Cooper** (1858–1964), the educator, scholar and author of *A Voice from the South* (1892). It was built for Homework 4 (End-to-End QA Pipeline) of 11-697 Introduction to Question Answering with Large Language Models, Fall 2026.

**Team members:** `<TEAM MEMBER 1>`, `<TEAM MEMBER 2>`, `<TEAM MEMBER 3>`

**Assigned person:** Anna Julia Cooper

## Usage

```python
from datasets import load_dataset

corpus = load_dataset("<username>/<corpusname>", split="train")
# corpus[i] -> {"title": ..., "pageid": ..., "text": ...}
by_title = {row["title"]: row for row in corpus}

repo = "hf://datasets/<username>/<corpusname>"
questions = load_dataset("json", data_files={
    "dev": f"{repo}/questions/questions_dev.jsonl",
    "test": f"{repo}/questions/questions_test.jsonl",
})
dev, test = questions["dev"], questions["test"]
```

The repository has a single config, the corpus. The `datasets` library reads every file in a repository with one format, so the JSONL question files are loaded with the `json` builder rather than as a second config.

## Files

| File | Rows | Contents |
|---|---|---|
| `corpus/corpus.csv` | 134 | Context documents: `title`, `pageid`, `text` (same schema as [bbasavar/wiki-corpus-v1](https://huggingface.co/datasets/bbasavar/wiki-corpus-v1)) |
| `corpus/sources.csv` | 134 | Per-document manifest: source, URL, license, retrieval date, length, flags |
| `questions/questions_dev.jsonl` | 20 | Dev questions, 5 of each type |
| `questions/questions_test.jsonl` | 20 | Test questions, 5 of each type |

Paths are relative to this card. The Hugging Face dataset repository uses the same layout as `data/` in the GitHub repository: upload this `README.md` together with the `corpus/` and `questions/` folders. Leave out the `corpus/raw/` HTML cache.

## Context corpus

### Sources

All text is real text from public sources; none of it was written by a language model (see [Known issues](#known-issues) for one tagged article).

| Source | Documents | License |
|---|---|---|
| English Wikipedia | 123 | CC BY-SA 4.0 |
| English Wikisource: *A Voice from the South* (1892) | 11 | Public domain |

Total: 134 documents, about 3.36 million characters (median 14,955 characters per document; shortest 357, longest 120,844). All pages were retrieved on 2026-11-15.

### Collection methodology

The corpus was collected with `data/corpus/crawl_cooper.py` in four layers, so that it covers Cooper and the people, places, events and works linked to her:

1. **Cooper's article** (1 document): the English Wikipedia article "Anna J. Cooper".
2. **First hop** (60 documents): articles linked from the body of Cooper's article, such as Oberlin College, M Street High School, Frelinghuysen University, the First Pan-African Conference, the Colored Women's League, Mary Church Terrell and Kadir Nelson. Links from the references, bibliography and navigation boxes were not followed. Generic pages (degree names, countries, citation identifiers such as ISBN or JSTOR, publishers, "List of" pages) were excluded.
3. **Second hop** (48 documents): up to six new articles linked from each of eight core pages (M Street High School, Frelinghuysen University, First Pan-African Conference, Colored Women's League, A Voice from the South, Saint Augustine's University, World's Congress of Representative Women, American Negro Academy). These give multi-hop questions entities to chain through, for example Cooper → Frelinghuysen University → Jesse Lawson.
4. **Seed list** (14 new documents): hand-picked related and near-miss articles, mostly Black women educators, writers and club leaders of Cooper's era (for example Fannie Barrier Williams, Nannie Helen Burroughs, Lucy Craft Laney). These are near-misses for unanswerable questions: relevant to the topic, but without the answer.
5. **Primary source** (11 documents): the full text of *A Voice from the South* from Wikisource, one document per essay, plus the title page.

**Text processing.**
- Article text is extracted from the page HTML.
- Section headings are kept as `== Heading ==` lines. Infobox rows become `Label: value` lines.
- Footnote markers, reference lists, "See also", "Further reading" and "External links" sections, navigation boxes and maintenance banners are removed.
- Documents shorter than 300 characters are dropped.

**Compliance.**
- Only `/wiki/<Title>` pages were fetched, and each URL was checked against the site's robots.txt, which disallows `/w/` and `/api/` for generic crawlers.
- Requests were sequential, at most one every 1.5 seconds, with backoff on HTTP 429.

**Identifiers.**
- Wikipedia documents keep their real page id.
- Wikisource page ids come from a different id space, so they are stored as `1,000,000,000 + id` to avoid collisions.
- Wikisource document titles end in ` (Wikisource)`. For example, `A Voice from the South/The Higher Education of Woman (Wikisource)`.

To rebuild the corpus:

```bash
pip install -r requirements.txt
python data/corpus/crawl_cooper.py
```

Wikipedia pages change over time, so a rebuild on a later date can differ slightly. The committed `corpus.csv` is the version the questions were written against.

## Questions

### Schema

Each line of `questions_dev.jsonl` and `questions_test.jsonl` follows the HW1 task-corpus schema:

```json
{
  "answers": {"answer_start": [950], "text": ["Mary Church Terrell"], "context_index": [1]},
  "context": ["<verbatim paragraph from the corpus>"],
  "id": "c01",
  "question": "Which of Anna Julia Cooper's Oberlin classmates earned her M.A. in the same year as Cooper, ...?",
  "title": ["Anna J. Cooper"],
  "type": "complex"
}
```

- `context` holds gold evidence paragraphs copied verbatim from `corpus.csv`, and `title` the matching document titles.
- `context_index` is **1-indexed**: `context[context_index[i] - 1]` contains `answers.text[i]` starting at character `answers.answer_start[i]`.
- **Multi-hop** questions list every hop's paragraph in `context`. `context_index` points at the paragraph with the final answer.
- **Unanswerable** questions have `answers.text = [""]`, `answer_start = [-1]` and `context_index = [1]`. Their `context` and `title` are a near-miss passage that makes the question look answerable.
- `context`, `title` and `answers` are gold evidence for evaluation only. A retrieval system should receive only `question` and the corpus.

### Question types

| Type | Count | How they were written | Example |
|---|---|---|---|
| factoid | 10 | One short, typed answer (person, number, date, place, organization) from one document, about lesser-known details | "In which London building was the 1900 First Pan-African Conference, attended by Anna Julia Cooper, held?" → Westminster Town Hall / Caxton Hall |
| complex | 10 | Why, definition, relationship or event questions answered by a phrase from one document | "Why was Anna Julia Cooper forced to interrupt her doctoral studies at Columbia University in 1915?" → she adopted her late half-brother's five children |
| multi_hop | 10 | Chain two documents through a bridge entity linked to Cooper | "Frelinghuysen University, which Anna J. Cooper later led, had a school named after Cooper's mother. What was that school called?" → Hannah Stanley Opportunity School |
| unanswerable | 10 | Ask for details that are not in the public record (what she ate, wore or hummed), each paired with a near-miss passage | "What color dress did Anna Julia Cooper wear when she delivered her address at the 1893 World's Congress of Representative Women?" → unanswerable |

Questions target specific, lesser-known facts (exact figures, associates, minor events) rather than the most famous facts about Cooper, so that they test retrieval rather than the model's memory.

### Construction and quality checks

Questions are written in `data/questions/questions_draft.json`. Each one names its evidence document(s), a short anchor phrase that identifies the evidence paragraph, and the answer text. `data/questions/build_questions.py` then:

- takes the paragraph containing each anchor, copied verbatim from the corpus, as the context;
- computes `answer_start` and `context_index`, using the occurrence closest to the anchor when an answer appears more than once;
- fails if any answer is not verbatim in its context, if a multi-hop question cites fewer than two documents, or if an unanswerable question lacks a near-miss passage;
- writes a 50/50 dev/test split stratified by type, with a fixed seed.

`data/questions/check_duplicates.py` embeds all questions with `sentence-transformers/all-MiniLM-L6-v2` and flags any pair with cosine similarity ≥ 0.85. Three pairs were flagged and reworded; no pair is above the threshold now (the highest is 0.841).

To rebuild and check the questions:

```bash
python data/questions/build_questions.py
```

```bash
python data/questions/check_duplicates.py
```

## Known issues

- **Tagged article.** The Wikipedia article "Anna J. Cooper" carries a November 2025 maintenance tag noting it may incorporate text from a large language model. We kept it as Wikipedia's current article on our subject. It is the evidence for 21 of the 40 questions, and the tag is recorded in the `flags` column of `sources.csv`.
- **Inconsistencies in that article.** It gives Cooper's Oberlin M.A. as both 1887 and 1888, and her age at the doctorate as both 65 and 66. No question depends on these facts.
- **Short documents.** Two Wikisource documents are short section dividers ("Soprano Obligato", "Tutti Ad Libitum"), and the "Kelly Miller" article is a stub.
- **Generic documents.** A few broader articles reached through links (for example "Spanish–American War", "Socrates", "Liberia") are only loosely related to Cooper. They act as distractors for retrieval.
- **Small evaluation set.** With 20 test questions (5 per type), per-type scores move in steps of 20 percentage points, so small differences between systems are not meaningful.

## Licensing and attribution

Wikipedia text is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The source URL of every document is listed in `sources.csv`. *A Voice from the South* (1892) is in the public domain. The dataset as a whole is released under CC BY-SA 4.0.

## AI use

The crawler, the question build script and the duplicate check were written with AI assistance (Claude Code). Question drafts were also AI-assisted; the team verifies every question and gold answer against the corpus. Full details are in `AI_USE.md` in the project repository.
