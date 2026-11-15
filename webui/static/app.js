// Web UI for GET /answer. No dependencies.
(function () {
  const form = document.getElementById("ask");
  const input = document.getElementById("question");
  const submit = document.getElementById("submit");
  const result = document.getElementById("result");
  const answerEl = document.getElementById("answer");
  const sourcesBlock = document.getElementById("sources-block");
  const sourcesEl = document.getElementById("sources");
  const metaEl = document.getElementById("meta");
  const statusEl = document.getElementById("status");

  const TIMEOUT_MS = 65000; // the live test allows 60 s per question

  // Wikisource documents are titled "<page> (Wikisource)"; everything else is Wikipedia.
  function sourceUrl(title) {
    const ws = title.match(/^(.*) \(Wikisource\)$/);
    const page = (ws ? ws[1] : title).replace(/ /g, "_");
    const host = ws ? "en.wikisource.org" : "en.wikipedia.org";
    return `https://${host}/wiki/${encodeURIComponent(page).replace(/%2F/g, "/")}`;
  }

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.classList.toggle("error", Boolean(isError));
  }

  function render(data, seconds) {
    const unanswerable = data.answer_candidate.trim().toLowerCase() === "unanswerable";
    answerEl.textContent = data.answer_candidate;
    answerEl.classList.toggle("unanswerable", unanswerable);

    sourcesEl.replaceChildren();
    for (const title of data.sources) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = sourceUrl(title);
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = title;
      li.appendChild(a);
      sourcesEl.appendChild(li);
    }
    sourcesBlock.hidden = data.sources.length === 0;
    metaEl.textContent = `Answered in ${seconds.toFixed(1)} s`;
    result.hidden = false;
  }

  async function ask(question) {
    submit.disabled = true;
    result.hidden = true;
    setStatus("Thinking…");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    const start = performance.now();
    try {
      const resp = await fetch(`/answer?question=${encodeURIComponent(question)}`, {
        signal: controller.signal,
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(typeof body.detail === "string" ? body.detail : `HTTP ${resp.status}`);
      }
      render(await resp.json(), (performance.now() - start) / 1000);
      setStatus("");
    } catch (err) {
      setStatus(err.name === "AbortError" ? "The request timed out." : `Something went wrong: ${err.message}`, true);
    } finally {
      clearTimeout(timer);
      submit.disabled = false;
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (question) ask(question);
  });

  for (const button of document.querySelectorAll(".example")) {
    button.addEventListener("click", () => {
      input.value = button.textContent;
      ask(button.textContent);
    });
  }
})();
