*Fall 2026 | 11-697 Introduction to Question Answering with Large Language Models | HW*

---

# Homework Assignment 1: Task Curation

## Creating a Question Answering Dataset

- **Deliverable:** A .zip file with 80 question-answer rows, and a reflection memo.
- **Due:** 9/14, 11:59pm US Eastern Time.

---

## I. Background

For this assignment, we have prepared a corpus of English Wikipedia articles, reconstructed into a single file, `corpus_v1.jsonl`, which is around 20 MB and has one JSON object per article with the following attributes: `title`, `pageid`, `text`.

## II. Usage

The following is the link to the corpus on HuggingFace, which we will be referring to as HF interchangeably.

- **Link:** [https://huggingface.co/datasets/bbasavar/wiki-corpus-v1](https://huggingface.co/datasets/bbasavar/wiki-corpus-v1)
- **HF Usage Instructions:**

```python
from datasets import load_dataset
corpus = load_dataset("bbasavar/wiki-corpus-v1", split="train")
# corpus[i] -> {"title": ..., "pageid": ..., "text": ...}
by_title = {row["title"]: row for row in corpus}
```

- **Schema for Submission:**

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

**Clarification:** The `context_index` list must mention the index of the context needed to arrive at the answer of the same index, i.e. `context[context_index[i]]` contains `answer[i]`. Multiple answers may come from the same context: In which case, the `context_index` list would have the same index repeated for those answer indices. You may treat it like a 1-indexed list. Say if context = {"aaa", "b", "cc" } and aaa serves as the context to the first three answers then you may mark it as [1, 1, 1, …].

Similarly, for multi-hop questions, you may need multiple contexts; in `context_index`, just list the context that provides the final answer (i.e. the final "hop"). For example, for the question "What is the population of the capital of France," let's say document A says "the population of Paris is 1 million," while document B says "the capital of France is Paris." For `context_index`, just list the index of A, but include both A and B in `context`. In other words, list all contexts in "context" and use the `context_index` to specify which single context answers each question.

For example,

```json
{
       "answers": {
            "answer_start": [23],
            "text": ["Paris"],
            "context_index" : [1]
       },
       "context": ["The capital city of France is Paris."],
       "id": "example_001",
       "question": "What is the capital of France?",
       "title": "France",
       "type": "factoid"
}
```

Make sure you write correct code to check the validity of your schema and final `submission.jsonl` file!

## III. Guidelines

- You are tasked with extending this corpus into a formal dataset.
- You must work only on the provided corpus database. Do NOT consult live Wikipedia since the article texts could have drifted. The corpus was frozen at the cutoff date, and your character offsets will not validate.
- Read Section IV and V carefully to understand how to proceed.
- We will be administering a 10% penalty if the total malformed or duplicate rows crosses 10% of the rows in your submission. In future assignments, we will be combining the class' submissions into a broader dataframe. So please adhere to the schema, as we will drop rows if they are malformed.

## IV. Steps

**1. Set up and audit:** Load `corpus_v1.jsonl` (from HF) and load it into a dictionary keyed by article title. The loading code is already given to you in the Usage section above. Once loaded, `by_title["Super_Bowl_50"]["text"]` gives you the full article text. You don't need to read everything; you're just getting oriented before you start choosing which articles to write questions about.

**2. Pick articles.** Select 8-10 articles. That's usually enough to comfortably write 80 rows without repeating yourself, roughly 5-8 rows per article and multi-hop questions combining articles. The selection methodology is up to you; you can either create a random sample or manually pick articles of interest/with lots of content etc.

**3. Write 80 rows** of questions adhering to the quotas below. Every row needs an exact evidence span (context) copied verbatim from the corpus text.

| Type | Count | Requirement |
|---|---|---|
| factoid | 20 | Answer is a parsable data type found in a contiguous span in one article, e.g. Date, Number, Person, Organization, Location; Answered by a single nugget (Nugget may appear in multiple nearly identical sentence-forms ex. JFK, John F Kennedy). |
| complex | 20 | Answer is in one article but is more complex than a factoid: Definition, Biography, Relationship, Event, Why; Answered by one or more nuggets. |
| multi_hop | 20 | Requires combining >=2 articles; list all in titles. |
| unanswerable | 20 | Seems plausible that the article would answer the question (i.e. it's relevant to that topic), but the answer is genuinely absent from the article. |

For unanswerable rows, set `answers["text"]` to `""` and `answer_start` to `-1`, and use context for the passage that makes the question look answerable (i.e. don't create a question that is completely unrelated to the article(s), as that would not be challenging enough for the model). For example, a passage like "The 45th and 47th US presidents were both Donald Trump" might qualify as looking like it could answer the question "Who was the 46th president of the US."

**4. Deduplicate.** Before submitting, check your own 80 questions pairwise for near-duplicates (e.g. embed with `sentence-transformers/all-MiniLM-L6-v2` and flag any pair with cosine similarity ≥ 0.85. [This Colab notebook](https://colab.research.google.com/drive/1PM_03eUzyGKm-Ld8XT1AkBAzdVbeQUpk#scrollTo=25N8-WYegdWo) contains the script to check duplicates described above. This is just an example, feel free to use a different technique, either automated or manual). Rewrite any flagged pair so both rows ask something meaningfully different. Make sure to run the duplicate check once again to re-verify.

**5. Write the reflection memo** (`reflection.md`, max 800 words). Answer all three questions below:

- Describe your approach to picking articles: what did you notice about which topics were easy vs. hard to write good questions for?
- Describe your approach to checking for duplicate questions. Did you use the provided script, do it manually, or use another method?
- Describe one question you considered during drafting that you chose not to include in the final dataset. Explain why you revised or removed it. (for example, because it was too similar to another question, ambiguous, unsupported by the corpus, or not a good fit for the assignment requirements.)
- Provide an hh:mm estimate for how long it took you to complete this assignment.

**6. Submit** a zip containing `submission.jsonl`, `reflection.md`, and any code you wrote.

## V. Use of AI tools

You may use LLMs for code (parsing, embedding, plotting) and for proofreading. You may NOT use them to generate questions, answers, evidence spans, or any part of the reflection memo.

Declare any AI use in a `AI_USE.md` file. Undeclared use found by TAs is an Academic Integrity Violation.
