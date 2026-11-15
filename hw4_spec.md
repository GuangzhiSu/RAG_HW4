*Fall 2026 | 11-697 Introduction to Question Answering with Large Language Models | HW*

---

# Homework Assignment 4: End-To-End QA Pipeline

## Implementing and Evaluating Retrieval-Augmented Generation

- **Deliverable:** A .zip file with implementation/evaluation code and a written report.
- **Due:** Friday 12/4, 11:59pm US Eastern Time.
- This assignment can be completed in groups of 1-3 people.

---

## I. Background

For this assignment, your team will be assigned a famous person, and you will build a corpus about them. The corpus should follow the format of the task corpus we have been using for HW1-3, meaning:

- The context documents have the same schema as [https://huggingface.co/datasets/bbasavar/wiki-corpus-v1](https://huggingface.co/datasets/bbasavar/wiki-corpus-v1), i.e. `title`, `pageid`, and `text` columns.
- The final corpus should have the same schema per question as you were asked to follow in HW1:

```json
{
  "answers": {
     "answer_start":["<start_position_1>","<start_position_2>","...", "<start_position_n>"],
     "text": ["<answer_1>", "<answer_2>", "...", "<answer_n>"],
     "context_index": ["<k_index_1>", "<k_index_2>", ..., "<k_index_n>"]
  },
  "context": ["<context_1>", "<context_2>", "...", "<context_k>"],
  "id": "<unique_example_id>",
  "question": "<question about the context>",
  "title": ["<title_1>", "<title_2>", "...", "<title_k>"],
  "type": "factoid" | "complex" | "multi_hop" | "unanswerable",
}
```

Note: as with HW1-3, `context`, `title`, and `answers` here are not your corpus and not inputs to your retriever or generator: they're the gold evidence for each question. Your retriever's only inputs are `question` and your context document corpus.

## II. Usage

You will upload your context document corpus to HuggingFace, and then call it.

- HF Usage Instructions:

```python
from datasets import load_dataset
corpus = load_dataset("username/corpusname", split="train")
# corpus[i] -> {"title": ..., "pageid": ..., "text": ...}
by_title = {row["title"]: row for row in corpus}
```

- `type` is factoid, complex, multi_hop or unanswerable.
- `title` is the gold article list for an answerable question. For an unanswerable question, the title is a relevant near-miss article.
- Your retriever will be given the question string and your context document corpus. It is NOT supposed to be given `title`, `context` or `answers` for the question it is ranking. Your generator will be given the top contexts as returned by your retriever, along with the question string.

## III. Guidelines

- Read the Steps and Evaluation sections carefully before you start.
- Your code must work when we load your corpus directly with `load_dataset("username/corpusname", ...)` as shown above. You may keep it private while you work, but make it public by the deadline.
- Cover your assigned person and the people, places, events and works linked to them, so you can write questions of all four types. Multi-hop and unanswerable questions need a corpus with linked entities and near-miss documents; plan for them when you build the corpus, not after.
- Start early. Building the corpus and questions takes longer than it looks.
- You are free to use all the remaining credits for this assignment (limit 100 dollars)
- Collect text only from sources that allow it: follow robots.txt and each site's terms. Wikipedia, Wikisource, Project Gutenberg and public archives are good places to start.
- Several teams may be assigned the same person, but each team builds its own corpus and questions. Copying another team's corpus or questions is an Academic Integrity Violation.

## IV. Steps

You will be designing and building an end-to-end RAG system for your assigned person, comparing the effects of different variants of the components of the system, adding capabilities a basic pipeline lacks, and writing a report that explains your design process.

### 1) Context Document & Task Curation

- Build your corpus around the famous person assigned to your team. You will receive your assigned person by email approximately a day after your team is finalized via team formation form.
- Create a context document corpus of **at least 100 documents**, with `title`, `pageid`, and `text` columns, formatted as a csv. The corpus must be real: text from public sources, not written by an LLM.
- Upload your context document corpus using the instructions at [https://huggingface.co/new-dataset](https://huggingface.co/new-dataset). Fill in the dataset card with the names of your team members, the name of your assigned person, and a description of the methodology behind how you collected the corpus.
- Because your person is famous, the LLM probably already knows many answers without retrieval. The closed-book run in Step 3 shows how many; the hidden questions in the Step 7 live test target facts the model is unlikely to know, so a working retrieval step is what earns those points.

### 2) Task Corpus Creation

- Use the process you followed in HW1 to turn your context document corpus into a task corpus with the schema as described in the first code block of Section I. Background.
- You should have **at least 40 questions**, evenly split across factoid, complex, multi-hop, and unanswerable.
- Ask about specific, lesser-known facts (minor events, exact figures, names of associates), not only the most famous ones. The model already knows the famous facts, so they don't test your retrieval.
- Every answerable question's gold answer must appear verbatim in the gold context, and every unanswerable question must have a near-miss title. An unanswerable question asks for something that is not in the public record (e.g. "What did \<person\> eat for breakfast on June 3, 1921?"), not just something missing from your corpus.
- Split your questions into **dev (50%) and test (50%), stratified by type**. Tune everything on dev. Run on test only for the required runs listed under evaluation, and never change your system based on test results.
- Upload the task corpus to Hugging Face alongside the context corpus (e.g. as `questions_dev.jsonl` and `questions_test.jsonl`).

### 3) Baselines

Build two baselines before changing anything, and run both on dev and test.

- **Closed-book:** your generator answers from the question alone, with no retrieval. This shows how much your corpus actually matters.
- **Baseline RAG (`baseline_rag`):** the pipeline you built in HW3 (RRF over sparse + dense retrieval, context re-ranking, generation, answer re-ranking), pointed at your new corpus with no other changes.

Every team uses the same generator LLM, **Llama 3.1 8B Instruct** (`us.meta.llama3-1-8b-instruct-v1:0` on the AI Gateway), for every run in this assignment and record it in `config.json`.

### 4) Required capabilities

`baseline_rag` retrieves once, abstains only if the prompt tells it to, and cites whatever titles the LLM names. Add each of the three capabilities below with a mechanism beyond prompt wording, and compare it against the HW3 pipeline on the relevant subset of dev and test.

| Capability | What the baseline pipeline does | What you must add (one or more) | Measured on |
|---|---|---|---|
| **Multi-hop** | One retrieval pass on the raw question | Query decomposition into sub-questions; iterative retrieve-then-read; follow-up queries built from intermediate answers | multi_hop EM; source recall |
| **Abstention** | Answers "unanswerable" only if the prompt says so | A confidence threshold calibrated on dev (e.g. answer likelihood, agreement across samples); a verifier or NLI check that the evidence supports the answer | unanswerable EM, and EM on answerable questions (to catch over-abstaining) |
| **Citation** | Lists whatever titles the LLM names | Citing numbered chunks mapped back to titles; dropping sources that don't contain or support the answer; post-hoc attribution | source precision and recall |

For abstention, also report how often the system wrongly abstains on answerable questions. An abstention method that wins on unanswerable questions by refusing everything is not an improvement.

### 5) Additional improvements

Make 1-2 further substantial changes. A substantial change alters a mechanism, not just a hyperparameter or the wording of a prompt. Choose them based on where your Step 3 baselines fail on dev. Examples:

- **Corpus processing:** chunking that fits your documents (by section, sentence windows, overlap); prepending titles to chunks.
- **Retrieval:** query rewriting or HyDE; a different or fine-tuned dense retriever; a retriever trained on your dev questions' gold titles.
- **Re-ranking:** a different cross-encoder; diversity across documents; a larger re-ranking pool.
- **Generation:** reason-then-answer prompting; few-shot examples drawn from dev; self-consistency voting over candidates.
- **Domain-specific:** anything your domain needs, such as handling tables, dates, numbers or units.

### 6) Final System

Combine the changes that helped on dev into one final system. Run it once on a test. Then run one ablation per Step 4 capability: the final system with that capability removed, also on test. This final system is the one you deploy in Step 7.

### 7) Deployment and live test

Deploy your final system anywhere that gives it a public HTTPS URL (for example Hugging Face Spaces, Render, Railway or Google Cloud Run), so that we can send it questions. Your endpoint must answer a GET request with the question in the URL:

```
curl -G "https://<your-url>/answer" --data-urlencode "question=<question>"
```

and return JSON in the same format as one entry of `answers` in your run files:

```
{"answer_candidate": "<short answer or unanswerable>", "sources": ["<title>", "..."]}
```

- Put your endpoint's base URL in `README.md`. It must be reachable without a login.
- Keep API keys in your host's secret settings, never in your code. The live test runs on your AI Gateway key; it is about 30 questions, so the cost is small.
- The live test will be run shortly after the last allowed late day (exact day to be announced). Your endpoint must be up all day that day.
- We send about 30 hidden questions about your assigned person, covering all four question types. They ask about specific, lesser-known facts. The unanswerable ones ask for things that are not in the public record, and the correct response to them is exactly `unanswerable`.
- We only check whether each answer is correct. Answers are scored with `exact_match` against our gold answers, and a TA reviews every answer that does not match, so a correct answer in other words still counts.
- **Live points = 25 × min(1, your accuracy ÷ 0.80).** You earn all 25 points at 80% accuracy or above; for example, 60% earns 18.75 points.
- Your endpoint must answer each question within 60 seconds. We retry a failed question once; if it fails again, it counts as wrong. Free hosts often sleep when idle, so wake yours up before the live test run date.
- During the live test you should use the model through AI Gateway only.
- **Bonus, up to +5:** a web UI for your system (+2), and one of the three highest live-test scores in the class (+3).
- If this is your first time deploying, refer to [this document](https://docs.google.com/document/d/1Uvx6MzTC-_iqUoC5VBTyZDcdG969V-8af1jblXaoizo/edit?tab=t.0) on how to deploy.

## V. Output format

Every run file `runs/<split>/<run_name>.jsonl` has one row per question, in this schema (same as HW3):

```json
{
  "answers": [{"answer_candidate": "<short answer or unanswerable>", "sources": ["<title>", "..."]}, "..."],
  "id": "<unique_example_id>",
  "question": "<question>",
  "type": "factoid" | "complex" | "multi_hop" | "unanswerable",
  "context_titles": ["<title of each chunk given to the generator>", "..."]
}
```

- Only `answers[0]` is scored. You may return one candidate or several.
- `answer_candidate` is a short answer (a span or short phrase), or exactly "unanswerable" with `sources: []`.
- `sources` lists the titles cited for that answer, each once.
- `context_titles` lists the titles of the chunks the generator saw. For multi-step systems, include every chunk seen across all steps.
- `type` is copied from the question file for scoring only. Your system must not read it.

## VI. Evaluation

Implement the following evaluation metrics based on the highest-ranked answer candidate for each question:

- **Exact match** with gold answer
  - If there are multiple gold answers, you can count an answer as correct if it contains any one of the gold answers
  - Your match can be "fuzzy" in that you can get rid of punctuation, tabs, and newlines, and be case-insensitive
- **Mean Precision of sources:** proportion of titles listed in "sources" that are valid (i.e. also in the "titles" in the reference entry for the question), and then take the mean over all questions
- **Mean Recall of sources:** proportion of valid titles (in the reference entry) that are listed in "sources," and then take the mean over all questions
- **Required runs**, each on dev and test (`runs/<split>/<run_name>.jsonl`):
  - `closed_book`, `baseline_rag` (Step 3)
  - `multihop`, `abstain`, `cite`: `baseline_rag` plus that one capability (Step 4)
  - `improve_1` (and `improve_2` if you make two changes): `baseline_rag` plus that one change (Step 5)
  - `final`, `final_no_multihop`, `final_no_abstain`, `final_no_cite` (Step 6)

## VII. Report & Submission

Submit `Report.pdf` with the sections below. All numbers must match `eval_generation.py` on your submitted run files.

1. **Corpus and task** (300 words or less). Your assigned person, how you built the context corpus (sources, size, and how you covered the people, places, events and works linked to them) and how you wrote each question type. Give one example question per type.
2. **System design** (600 words or less, plus one diagram). Your final system, stage by stage, and why each piece is there. Describe each Step 4 mechanism and each Step 5 change precisely enough that a reader could re-implement it. This section must match the code in `src/`.
3. **Main results table.** One row per required run, on test. Columns: EM overall, EM per type (factoid, complex, multi_hop, unanswerable), mean source precision, mean source recall, false abstention rate. Put the same table for dev in an appendix.
4. **Comparisons.** For each of the following, report the change in the relevant metrics and explain what caused it, with at least one concrete example question from your runs:
   - `closed_book` vs Baseline: how much does retrieval help on your corpus?
   - Baseline RAG vs `multihop`, `abstain` and `cite`, each on its target metric.
   - Baseline RAG vs each `improve_k`.
   - `final` vs each `final_no_*` ablation: which capability matters most in the combined system?
5. **Error analysis.** Pick at least 5 test questions your final system gets wrong (a wrong answer, a missed or wrong abstention, a missed source or a false-positive source), from at least three question types. For each: the question, what is wrong, and your hypothesis for why. Use `context_titles` to say whether retrieval, re-ranking or generation was at fault.
6. **Limitations.** What your evaluation can and cannot show, given the size of your test split and how your questions were written.

In addition to a group report, each team member of a 2- or 3-person team must also fill out [this peer review form](https://forms.gle/b66PocHVGzixnr2P8) declaring exactly what each team member contributed to the assignment. Solo teams don't need to do this.

Submit one zip per group containing:

```
Report.pdf

README.md          HF dataset names and your endpoint URL; how to
reproduce every run file from a clean environment, top to bottom

AI_USE.md

requirements.txt

config.json                    generator model, decoding settings, all
hyperparameters

src/

   metrics.py

   eval_generation.py                unchanged

   (your system modules)

data/

   corpus.csv

   questions_dev.jsonl

   questions_test.jsonl

runs/

   dev/<run_name>.jsonl                     every required run

   test/<run_name>.jsonl                    every required run
```

- The README must work when TAs follow it literally. They will load your corpus with `load_dataset("username/corpusname")`.
- Read API keys from environment variables named in the README. Do not commit them.
- Grading uses your submitted run files and the live test (Step 7). Run `pytest tests/` before you submit.

## VIII. Grading

| Component | Points |
|---|---|
| Corpus quality, coverage and task creation (Steps 1–2, report section 1) | 10 |
| Baselines (Step 3) | 5 |
| Multi-hop mechanism and its comparison | 8 |
| Abstention mechanism and its comparison | 8 |
| Citation mechanism and its comparison | 8 |
| Additional improvements (Step 5) | 6 |
| Evaluation metrics (`metrics.py`, graded by tests) | 5 |
| System design (report section 2) | 5 |
| Results and comparisons (report sections 3–4) | 10 |
| Error analysis and limitations (report sections 5–6) | 5 |
| Deployment (Step 7) | 5 |
| Live test (Step 7) | 25 |

- **Total: 100 points**
- **Bonus, up to +5:** a web UI for your system (+2) and one of the three highest live-test scores in the class (+3)
- Groups are graded to the same standard regardless of group size (i.e. same amount of work is expected for a 3-person team as a solo team) but will receive individual grades, so make sure to contribute your fair share to your team!

### Penalties

- Code doesn't run from the README, or the corpus can't be loaded from Hugging Face: −5.
- Using a question's gold `context`, `title`, `answers` or `type` at any stage of the system: 0 for that method.
- Tuning on the test split: 0 for the comparisons section.
- Report numbers don't match `eval_generation.py` on your submitted run files: −10.
- Hard-coded or hand-edited run outputs: 0 for that run.
- A design section that doesn't match the code in `src/`: 0 for the design section.
- Fewer questions or documents than required: −5.
- Your endpoint doesn't run the code in your submitted `src/`: 0 for the live test.
- Your endpoint is unreachable during the live test window: 0 for the live test.
- Work submitted after the live test has run gets a 0 for the live test.
- Failure to fill out the [team member contribution form](https://forms.gle/b66PocHVGzixnr2P8) (teams of 1 are exempt): -15 for that team member.
- Individual contribution significantly less than others in the group: deduction on a case-by-case basis depending on severity of the contribution gap.

**Late policy:** 10% per day for up to 5 days; 0 after that.

## IX. Use of AI tools

You may use LLMs to proofread code, help write your README, and help draft or format corpus documents and questions, as long as you check every question and gold answer yourself. You may NOT use LLMs to design or implement your retrieval, generation, multi-hop, abstention or citation components without first making a genuine effort to implement them yourself.

Declare all AI use in `AI_USE.md`: list every tool, what you used it for, which files it modified, and what you attempted yourself before using it. Undeclared use found by TAs is an Academic Integrity Violation.
