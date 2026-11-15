#!/usr/bin/env python3
"""Build the Anna Julia Cooper context-document corpus.

Output: data/corpus/corpus.csv with columns title, pageid, text (same schema as
bbasavar/wiki-corpus-v1), plus data/corpus/sources.csv, a manifest with the source
URL, license and quality flags of every document.

Sources
-------
* English Wikipedia: Cooper's article, every article it links to from its body
  (the people, places, institutions, events and works linked to her), and a
  hand-picked list of related and near-miss articles (SEED_TITLES).
* English Wikisource: the full text of "A Voice from the South" (1892), one
  document per essay. The book is in the public domain.

Politeness / terms
------------------
* Only /wiki/<Title> pages are fetched. Wikimedia's robots.txt disallows /w/
  and /api/ for generic crawlers, so the API is not used. Every URL is checked
  against the host's robots.txt before it is fetched.
* Requests are sequential, at most one every --delay seconds (default 1.5s),
  with exponential backoff on HTTP 429/5xx and respect for Retry-After.
* Raw HTML is cached in data/corpus/raw/, so reruns do not hit the sites again
  (use --refresh to refetch).
* Wikipedia text is CC BY-SA 4.0; the manifest records the URL of every
  page so the dataset card can attribute it.

pageid
------
Wikipedia documents keep their real Wikipedia page id. Wikisource page ids
live in a different id space, so they are stored as WIKISOURCE_OFFSET + id to
avoid collisions. Titles of Wikisource documents end in " (Wikisource)".

Usage
-----
    python data/corpus/crawl_cooper.py                 # crawl + write data/corpus/corpus.csv
    python data/corpus/crawl_cooper.py --max-linked 80 # cap the 1-hop Wikipedia links
    python data/corpus/crawl_cooper.py --skip-llm-flagged
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

DATA_DIR = Path(__file__).resolve().parent
RAW_DIR = DATA_DIR / "raw"
USER_AGENT = "HW4-corpus-builder/0.1 (course project; python-requests)"
WIKIPEDIA = "en.wikipedia.org"
WIKISOURCE = "en.wikisource.org"
WIKISOURCE_OFFSET = 1_000_000_000
MIN_CHARS = 300

COOPER_ARTICLE = "Anna Julia Cooper"
BOOK_ROOT = "A Voice from the South"

# Related and near-miss Wikipedia articles that Cooper's article may not link
# to directly. Near-misses (contemporary Black women educators and writers,
# similar institutions) are what unanswerable questions need: they look
# relevant to a question but do not answer it. Titles that do not exist are
# reported and skipped.
SEED_TITLES = [
    # Her work and the institutions in her life
    "A Voice from the South",
    "Saint Augustine's University",
    "Oberlin College",
    "Dunbar High School (Washington, D.C.)",
    "University of Paris",
    "Frelinghuysen University",
    "Wilberforce University",
    "Columbia University",
    "Raleigh, North Carolina",
    "Washington, D.C.",
    "LeDroit Park",
    # Events and organizations
    "1900 Pan-African Conference",
    "World's Congress of Representative Women",
    "World's Columbian Exposition",
    "Colored Women's League",
    "National Association of Colored Women's Clubs",
    "American Negro Academy",
    "Hampton Negro Conference",
    "Black feminism",
    "Womanism",
    # Associates and contemporaries (also near-misses)
    "W. E. B. Du Bois",
    "Booker T. Washington",
    "Alexander Crummell",
    "Francis James Grimké",
    "Charlotte Forten Grimké",
    "Mary Church Terrell",
    "Ida B. Wells",
    "Frances Harper",
    "Fannie Jackson Coppin",
    "Fannie Barrier Williams",
    "Hallie Quinn Brown",
    "Josephine St. Pierre Ruffin",
    "Nannie Helen Burroughs",
    "Mary McLeod Bethune",
    "Lucy Craft Laney",
    "Mary Jane Patterson",
    "Benjamin W. Arnett",
    "Henry Highland Garnet",
    "Carter G. Woodson",
    "Jesse Lawson",
    "Kelly Miller",
    "Paul Laurence Dunbar",
    "Albion W. Tourgée",
    "Célestin Bouglé",
]

# Core pages whose own links are also followed (a capped second hop), for
# multi-hop questions that chain from Cooper through an institution or event.
HOP2_TITLES = [
    "M Street High School",
    "Frelinghuysen University",
    "First Pan-African Conference",
    "Colored Women's League",
    "A Voice from the South",
    "Saint Augustine's University (North Carolina)",
    "World's Congress of Representative Women",
    "American Negro Academy",
]

# Linked articles that are too generic to be useful (degree names, countries,
# common concepts). They would only add noise.
GENERIC_LINKS = {
    "PhD", "Doctor of Philosophy", "Bachelor of Arts", "Master of Arts",
    "United States", "United States of America", "France", "Paris",
    "English language", "French language", "Latin", "Greek language",
    "Mathematics", "Science", "History", "Sociology", "Slavery",
    "Slavery in the United States", "African Americans", "Christianity",
    "Episcopal Church (United States)", "Feminism", "Women's suffrage",
    "Civil rights movement", "American Civil War", "Racism", "Education",
    "Teacher", "Principal (school)", "Public domain", "Wikisource",
    "Wikidata", "Wikimedia Commons", "Library of Congress", "Birth name",
    # citation identifiers, databases and publishers
    "ISBN", "OCLC", "Digital object identifier", "JSTOR", "Semantic Scholar",
    "Find a Grave", "PubMed", "ISSN", "Bibcode", "S2CID", "Hdl (identifier)",
    "Oxford University Press", "Dover Publications", "Edwin Mellen Press",
    "Globe Pequot Publishing Group", "Black Classic Press", "Wiley (publisher)",
    "Routledge", "Rowman & Littlefield", "Lewiston, New York",
    # generic pages reached on the second hop
    "Coalition", "The truth will set you free", "Private university",
    "Secondary education", "Higher education accreditation",
    "Historic districts in the United States", "Non-denominational Christianity",
    "Romanesque Revival architecture", "National Register of Historic Places",
    "Black women", "London", "Chicago",
}

# Section headings dropped from Wikipedia articles (case-insensitive).
DROP_SECTIONS = {
    "see also", "notes", "references", "reference bibliography", "citations",
    "sources", "further reading", "external links", "footnotes",
    "bibliography (references)", "notes and references",
}

# Elements removed before text extraction.
NOISE_SELECTORS = [
    "script", "style", "noscript", "sup.reference", "span.mw-editsection",
    ".mw-references-wrap", "ol.references", ".reflist", ".navbox",
    ".navbox-styles", ".vertical-navbox", ".sistersitebox", ".side-box",
    ".ambox", ".ombox", ".tmbox", ".hatnote", ".shortdescription",
    ".mw-empty-elt", ".noprint", ".metadata", ".authority-control",
    ".ws-noexport", ".pagenum", ".ws-pagenum", "#headertemplate",
    ".wst-header", ".ws-header", ".licenseContainer", ".mw-cite-backlink",
    "figure", ".thumb", ".gallery", "math", ".mwe-math-element",
]


class PoliteFetcher:
    """Sequential, cached, robots.txt-aware HTTP fetcher."""

    def __init__(self, delay: float, refresh: bool):
        self.delay = delay
        self.refresh = refresh
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last = 0.0

    def _wait(self):
        gap = time.monotonic() - self._last
        if gap < self.delay:
            time.sleep(self.delay - gap)
        self._last = time.monotonic()

    def _get(self, url: str) -> requests.Response:
        for attempt in range(6):
            self._wait()
            try:
                resp = self.session.get(url, timeout=30)
            except requests.RequestException as exc:
                print(f"  network error ({exc}); retrying", file=sys.stderr)
                time.sleep(5 * 2**attempt)
                continue
            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After", "")
                wait = int(retry_after) if retry_after.isdigit() else 10 * 2**attempt
                print(f"  HTTP {resp.status_code}; waiting {wait}s", file=sys.stderr)
                time.sleep(min(wait, 300))
                continue
            return resp
        raise RuntimeError(f"giving up on {url}")

    def allowed(self, url: str) -> bool:
        host = urlparse(url).netloc
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            resp = self._get(f"https://{host}/robots.txt")
            rp.parse(resp.text.splitlines() if resp.ok else [])
            self._robots[host] = rp
        return self._robots[host].can_fetch(USER_AGENT, url)

    def fetch(self, url: str) -> str | None:
        cache = RAW_DIR / urlparse(url).netloc / (
            hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")
        if cache.exists() and not self.refresh:
            return cache.read_text(encoding="utf-8")
        if not self.allowed(url):
            print(f"  robots.txt disallows {url}; skipped", file=sys.stderr)
            return None
        resp = self._get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(resp.text, encoding="utf-8")
        return resp.text


URL_SAFE = "/:(),.'!-"


def wiki_url(host: str, title: str) -> str:
    return f"https://{host}/wiki/{quote(title.replace(' ', '_'), safe=URL_SAFE)}"


def title_from_href(href: str, host: str) -> str | None:
    """Article title for an internal /wiki/ link, or None if not an article."""
    prefix = f"https://{host}/wiki/"
    if href.startswith("/wiki/"):
        href = f"https://{host}{href}"
    if not href.startswith(prefix) or "?" in href:
        return None  # external link, or a red link (?action=edit&redlink=1)
    title = unquote(href[len(prefix):].split("#")[0]).replace("_", " ")
    if not title or ":" in title.split("/")[0]:
        return None  # File:, Help:, Category:, Special:, Author:, ...
    return title


def js_config(html: str, key: str):
    match = re.search(rf'"{key}":("(?:[^"\\]|\\.)*"|-?\d+|true|false|\[[^\]]*\])', html)
    return json.loads(match.group(1)) if match else None


def clean_ws(text: str) -> str:
    text = text.replace("​", "").replace("\xa0", " ")
    text = re.sub(r"(?:\s*\.){4,}", " ", text)        # table-of-contents dot leaders
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def inline_text(node: Tag) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).replace(" ,", ",").replace(" .", ".")


def table_text(table: Tag) -> str:
    rows = []
    infobox = "infobox" in (table.get("class") or [])
    for tr in table.find_all("tr"):
        cells = [inline_text(c) for c in tr.find_all(["th", "td"])]
        cells = [c for c in cells if c]
        if not cells:
            continue
        rows.append(": ".join(cells) if infobox and len(cells) == 2 else " | ".join(cells))
    return "\n".join(rows)


def wikipedia_text(content: Tag, links: list[str] | None = None) -> str:
    """Walk the article body in order, keeping headings, prose, lists and tables.

    Handles both flat bodies and bodies wrapped in nested <section> / <div>
    elements. Sections listed in DROP_SECTIONS (references etc.) are skipped
    along with all of their subsections. If `links` is given, the titles of
    internal article links in the kept parts are appended to it.
    """
    parts: list[str] = []
    skip_level = None  # level of the dropped heading we are inside, if any

    def visit(parent: Tag):
        nonlocal skip_level
        for node in parent.children:
            if not isinstance(node, Tag):
                continue
            classes = node.get("class") or []
            heading = None
            if node.name in ("h2", "h3", "h4", "h5"):
                heading = node
            elif "mw-heading" in classes:
                heading = node.find(["h2", "h3", "h4", "h5"])
            if heading is not None:
                name = inline_text(heading)
                level = int(heading.name[1])
                if skip_level is not None and level <= skip_level:
                    skip_level = None
                if skip_level is None and name.lower() in DROP_SECTIONS:
                    skip_level = level
                if skip_level is None:
                    marks = "=" * level
                    parts.append(f"\n{marks} {name} {marks}")
                continue
            if skip_level is not None and node.name not in ("section", "div"):
                continue
            if links is not None and node.name not in ("section", "div"):
                for a in node.select("a[href]"):
                    title = title_from_href(a["href"], WIKIPEDIA)
                    if title:
                        links.append(title)
            if node.name == "table":
                parts.append(table_text(node))
            elif node.name in ("p", "blockquote", "dl"):
                parts.append(inline_text(node))
            elif node.name in ("ul", "ol"):
                parts.extend(f"- {inline_text(li)}" for li in node.find_all("li", recursive=False))
            elif node.name in ("section", "div"):
                visit(node)

    visit(content)
    return clean_ws("\n".join(p for p in parts if p))


BLOCK_TAGS = ["p", "div", "li", "tr", "dd", "dt", "center", "blockquote",
              "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol"]


def block_text(content: Tag) -> str:
    """Plain text with newlines only at block boundaries and <br>.

    Used for Wikisource, whose scanned-book markup splits words across inline
    spans (drop caps, page-break markers), so get_text("\\n") would break them.
    """
    for br in content.find_all("br"):
        br.replace_with("\n")
    for el in content.find_all(BLOCK_TAGS):
        el.insert_after("\n\n" if el.name == "p" else "\n")
    return clean_ws(content.get_text(""))


def parse_page(html: str, host: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    if js_config(html, "wgNamespaceNumber") not in (0, None):
        return None
    if "Disambiguation pages" in (js_config(html, "wgCategories") or []):
        return None
    content = soup.select_one("#mw-content-text .mw-parser-output")
    if content is None:
        return None

    flags = []
    for box in content.select(".ambox"):
        msg = box.get_text(" ", strip=True).lower()
        if "large language model" in msg:
            flags.append("llm_text_tag")

    # Wikisource chapter links live in the header template, which the noise
    # selectors remove, so collect them first.
    links: list[str] = []
    if host == WIKISOURCE:
        links = [t for a in content.select("a[href]") if (t := title_from_href(a["href"], host))]

    for sel in NOISE_SELECTORS:
        for el in content.select(sel):
            el.decompose()

    if host == WIKIPEDIA:
        text = wikipedia_text(content, links)  # links only from kept sections
    else:
        text = block_text(content)

    return {
        "title": js_config(html, "wgTitle") or inline_text(soup.select_one("#firstHeading")),
        "pageid": js_config(html, "wgArticleId"),
        "text": text,
        "links": list(dict.fromkeys(links)),
        "flags": flags,
    }


def useful_links(titles: list[str]) -> list[str]:
    """Drop generic, list, identifier and year links."""
    return [t for t in titles
            if t not in GENERIC_LINKS
            and not t.startswith(("List of ", "Lists of "))
            and not t.endswith(" (identifier)")
            and not re.fullmatch(r"\d{3,4}s?", t)]


def crawl(args) -> list[dict]:
    fetcher = PoliteFetcher(args.delay, args.refresh)
    docs: dict[int, dict] = {}
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def add(host: str, title: str, origin: str) -> dict | None:
        url = wiki_url(host, title)
        html = fetcher.fetch(url)
        if html is None:
            print(f"  missing: {host} {title}", file=sys.stderr)
            return None
        page = parse_page(html, host)
        if page is None or not page["pageid"]:
            print(f"  skipped (not an article / disambiguation): {title}", file=sys.stderr)
            return None
        pid = page["pageid"] + (WIKISOURCE_OFFSET if host == WIKISOURCE else 0)
        if pid in docs:
            return docs[pid] if origin != "hop2_new" else None
        doc_title = page["title"] + (" (Wikisource)" if host == WIKISOURCE else "")
        page.update(
            title=doc_title,
            pageid=pid,
            source="wikisource" if host == WIKISOURCE else "wikipedia",
            url=wiki_url(host, page["title"]),
            license="Public domain" if host == WIKISOURCE else "CC BY-SA 4.0",
            origin=origin,
            retrieved_at=retrieved,
        )
        docs[pid] = page
        print(f"  [{len(docs):3d}] {doc_title} ({len(page['text'])} chars)")
        return page

    print("Wikipedia: Cooper's article")
    cooper = add(WIKIPEDIA, COOPER_ARTICLE, "cooper")
    if cooper is None:
        raise SystemExit("could not fetch Cooper's article")

    print("Wikipedia: articles linked from Cooper's article")
    for title in useful_links(cooper["links"])[: args.max_linked]:
        add(WIKIPEDIA, title, "linked_from_cooper")

    print("Wikipedia: second hop from core pages")
    for core in HOP2_TITLES:
        page = add(WIKIPEDIA, core, "hop2_core")
        if page is None:
            continue
        picked = 0
        for title in useful_links(page["links"]):
            if picked >= args.hop2_per_page:
                break
            if add(WIKIPEDIA, title, "hop2_new") is not None:
                picked += 1

    print("Wikipedia: related and near-miss seed articles")
    for title in SEED_TITLES:
        add(WIKIPEDIA, title, "seed")

    print("Wikisource: A Voice from the South")
    root = add(WIKISOURCE, BOOK_ROOT, "book")
    if root is not None:
        chapters = [t for t in root["links"] if t.startswith(BOOK_ROOT + "/")]
        for title in chapters:
            add(WIKISOURCE, title, "book")

    return list(docs.values())


def write_outputs(docs: list[dict], args):
    kept = []
    for d in docs:
        if len(d["text"]) < MIN_CHARS:
            print(f"  dropped (shorter than {MIN_CHARS} chars): {d['title']}", file=sys.stderr)
            continue
        if args.skip_llm_flagged and "llm_text_tag" in d["flags"]:
            print(f"  dropped (tagged as containing LLM text): {d['title']}", file=sys.stderr)
            continue
        kept.append(d)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "pageid", "text"])
        for d in kept:
            w.writerow([d["title"], d["pageid"], d["text"]])

    with open(args.manifest, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "pageid", "source", "origin", "url", "license",
                    "retrieved_at", "chars", "flags"])
        for d in kept:
            w.writerow([d["title"], d["pageid"], d["source"], d["origin"], d["url"],
                        d["license"], d["retrieved_at"], len(d["text"]), ";".join(d["flags"])])

    flagged = [d["title"] for d in kept if d["flags"]]
    print(f"\nWrote {len(kept)} documents to {args.out}")
    print(f"Wrote manifest to {args.manifest}")
    if len(kept) < 100:
        print(f"WARNING: only {len(kept)} documents; the assignment needs at least 100.")
    if flagged:
        print("WARNING: these pages carry a Wikipedia tag saying they may contain LLM-written "
              "text; review them (or rerun with --skip-llm-flagged):")
        for t in flagged:
            print(f"  - {t}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DATA_DIR / "corpus.csv")
    ap.add_argument("--manifest", type=Path, default=DATA_DIR / "sources.csv")
    ap.add_argument("--max-linked", type=int, default=150,
                    help="max number of articles linked from Cooper's article to include")
    ap.add_argument("--hop2-per-page", type=int, default=6,
                    help="new articles to add from the links of each HOP2_TITLES page")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    ap.add_argument("--refresh", action="store_true", help="ignore the raw HTML cache")
    ap.add_argument("--skip-llm-flagged", action="store_true",
                    help="drop pages Wikipedia tags as containing LLM-written text")
    args = ap.parse_args()
    write_outputs(crawl(args), args)


if __name__ == "__main__":
    main()
