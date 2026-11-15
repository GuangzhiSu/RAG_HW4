# HW4 plan for Anna Julia Cooper

**Due:** Friday 12/4, 11:59pm ET. The live test runs after the last late day.

## Flow chart

```
┌──────────────────────────────────────────────────────────────┐
│ PHASE A: DATA (Steps 1–2)                                    │
│                                                              │
│  Collect public texts ──► corpus.csv (≥100 docs:             │
│  (Wikipedia, Wikisource,   title, pageid, text)              │
│   Gutenberg, archives)          │                            │
│                                 ▼                            │
│                   Upload to HF + dataset card                │
│                                 │                            │
│                                 ▼                            │
│  Write ≥40 questions (10 factoid / 10 complex /              │
│  10 multi_hop / 10 unanswerable) in HW1 schema               │
│                                 │                            │
│                                 ▼                            │
│  Stratified split: dev 50% / test 50% ──► upload to HF       │
└─────────────────────────────────┬────────────────────────────┘
                                  ▼
┌──────────────────────────────────────────────────────────────┐
│ PHASE B: BASELINES (Step 3) — Llama 3.1 8B for every run     │
│                                                              │
│   closed_book (no retrieval)     baseline_rag (HW3 pipeline: │
│                                  RRF sparse+dense → rerank → │
│                                  generate → answer rerank)   │
│          └──────── run both on dev + test ───────┘           │
│                           │                                  │
│              Error analysis on DEV only                      │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ PHASE C: CAPABILITIES (Steps 4–5), each = baseline + 1 thing │
│                                                              │
│  multihop ─ decomposition / iterative retrieval              │
│  abstain  ─ calibrated confidence threshold / NLI verifier   │
│  cite     ─ numbered chunks → titles, drop unsupported       │
│  improve_1 (+ improve_2) ─ chosen from dev failures          │
│                                                              │
│  Tune on dev ──► run each on dev + test (test never tunes)   │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ PHASE D: FINAL (Step 6)                                      │
│  final = everything that helped on dev                       │
│  ablations: final_no_multihop / final_no_abstain /           │
│             final_no_cite   (all on test, plus dev)          │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ PHASE E: DEPLOY (Step 7)                                     │
│  GET /answer?question=... → {"answer_candidate","sources"}   │
│  public HTTPS, <60s, keys in host secrets, optional web UI   │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ PHASE F: REPORT + ZIP                                        │
│  Report.pdf (6 sections) · README · AI_USE.md · config.json  │
│  src/ · data/ · runs/dev + runs/test · pytest tests/ passes  │
└──────────────────────────────────────────────────────────────┘
```

## Step by step

### 1. Build the corpus (≥100 documents, real text only)
The list below was drafted from general knowledge. Check every fact against the sources before relying on it.
- **Main sources:**
  - Cooper's Wikipedia article.
  - Her book *A Voice from the South* (1892), split into one document per chapter or essay. Copies exist on Project Gutenberg and Documenting the American South; check each site's terms.
  - Her speeches and essays, for example her talk at the 1893 World's Congress of Representative Women.
- **Linked entities, needed for multi-hop questions:**
  - Places: Raleigh, NC; Oberlin College; Washington, D.C.
  - Schools and institutions: St. Augustine's (Normal School / College); M Street High School / Dunbar High School; the Sorbonne / University of Paris; Frelinghuysen University; Wilberforce University.
  - Events: the 1900 Pan-African Conference; the M Street High School controversy; her doctoral thesis on France's attitudes toward slavery in the Revolutionary era; the passport and stamp commemorations.
  - People: associates and contemporaries such as W.E.B. Du Bois, Mary Church Terrell, Alexander Crummell, Francis Grimké, Charlotte Forten Grimké, and Ida B. Wells.
- **Near-miss documents, needed for unanswerable questions:** similar figures (Black women educators and writers of the same era) and similar institutions, so that a question can retrieve related but non-answering text.
- **Upload:** a CSV with `title, pageid, text` to Hugging Face. Fill in the dataset card with team names, the person, and the collection method. Follow robots.txt and each site's terms.

### 2. Write the questions (≥40, 10 per type)
- **Factoid:** a lesser-known exact fact, for example a date, a figure, or the name of an associate.
- **Complex:** needs synthesis or reasoning over one document.
- **Multi-hop:** chains facts across ≥2 documents. For example: "What city was the institution where Cooper earned her doctorate located in, and who founded it?" Keep a list of the bridge entities.
- **Unanswerable:** asks for something not in *any* public record, and has a near-miss gold title. For example: "What did Cooper eat for breakfast the day she defended her dissertation?"
- Every answerable gold answer must appear verbatim in its gold context.
- Make a stratified 50/50 dev/test split, then freeze test and upload both files.

### 3. Baselines
- Set up `config.json` with `us.meta.llama3-1-8b-instruct-v1:0`, the decoding settings, and all hyperparameters.
- Write `closed_book` and `baseline_rag`, the HW3 pipeline pointed at the new corpus, and run both on dev and test.
- Write `src/metrics.py`: EM using normalized "contains any gold answer" matching, mean source precision, mean source recall, and false-abstention rate. Make sure `pytest tests/` passes.

### 4. The three required capabilities
Each one has to be a mechanism, not just prompt wording, and is tested as baseline plus that one change.

| Run | Suggested mechanism | Target metric |
|---|---|---|
| `multihop` | LLM decomposes the question into sub-questions; retrieve per sub-question; build follow-up queries from intermediate answers | multi_hop EM, source recall |
| `abstain` | Sample N answers and measure agreement and/or an NLI check that the evidence entails the answer; calibrate the threshold on dev | unanswerable EM, answerable EM, false-abstention rate |
| `cite` | Number the chunks, have the LLM cite numbers, map them back to titles, drop titles whose chunk doesn't contain or support the answer | source precision and recall |

### 5. Additional improvements (1–2 mechanism changes)
Pick these from where dev fails. Good candidates for this corpus:
- Section- or paragraph-based chunking of *A Voice from the South* with titles prepended to each chunk.
- HyDE or query rewriting.
- A larger reranking pool or a stronger cross-encoder.
- Normalizing dates and numbers in answers.

Run these as `improve_1` and `improve_2`.

### 6. Final system
- Combine the changes that helped on dev into `final` and run it once on test.
- Run the three ablations: `final_no_multihop`, `final_no_abstain`, `final_no_cite`.
- Required run files, 11 or 12 per split: closed_book, baseline_rag, multihop, abstain, cite, improve_1, (improve_2), final, and the 3 ablations.

### 7. Deploy
- Wrap `final` in a small FastAPI or Flask app with `GET /answer?question=` on a public HTTPS host such as HF Spaces, Render, Railway, or Cloud Run.
- Keep the AI Gateway key in the host's secret settings, never in the code. Each answer must come back in under 60 seconds.
- The endpoint has to run the submitted `src/` code. Wake it up before the live test day.
- Optional bonus: a web UI is worth +2.
- The live test is worth 25 points, the biggest single item, and is about 30 hidden questions on lesser-known facts. Wide corpus coverage of obscure details and reliable abstention matter most here.

### 8. Report and submission
- **Report sections:**
  1. Corpus and task (≤300 words).
  2. Design (≤600 words plus a diagram).
  3. Test results table, with the dev table in an appendix.
  4. Comparisons, with example questions.
  5. Error analysis (≥5 test errors across ≥3 types).
  6. Limitations.
- Every number must match `eval_generation.py` on the run files.
- The zip contains Report.pdf, README.md (HF names, endpoint URL, reproduction steps), AI_USE.md, requirements.txt, config.json, `src/`, `data/`, and `runs/`.
- Each teammate fills in the peer review form.

## Suggested timeline

| Dates | Milestone |
|---|---|
| 11/15–11/19 | Corpus collected and uploaded; questions written and split |
| 11/20–11/22 | Baselines and metrics done; dev error analysis |
| 11/23–11/28 | multihop, abstain, cite, improve_k (tuned on dev) |
| 11/29–11/30 | Final and ablations on test; deploy endpoint |
| 12/1–12/4 | Report, README, AI_USE.md, zip; check that the endpoint stays up |

## Things that cost points
- Reading `type`, `title`, `context`, or `answers` anywhere in the system scores 0 for that method.
- Tuning on test scores 0 for the comparisons section.
- Hand-edited run files score 0 for that run.
- A design section that doesn't match `src/` scores 0 for that section.
- Fewer than 100 documents or 40 questions costs 5 points.
- A README that doesn't run as written costs 5 points.
