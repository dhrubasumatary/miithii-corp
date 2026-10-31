"""Risk-path spike: hybrid retrieval quality + per-ticket cost model.

Throwaway de-risk tooling (2026-10-31). Measures, on a real product docs
corpus (astral.sh uv + ruff docs), whether hybrid retrieval (embedding
cosine + BM25, fused with RRF) beats naive embedding-only retrieval —
the load-bearing assumption behind miithii's RAG plan.

No services, no keys: fastembed (local ONNX model) for embeddings,
numpy for vector search, rank-bm25 for lexical. Numbers are printed and
written to spike/results/spike_results.json.

Caveats recorded in results: corpus is a docs proxy (not a real tenant's
help center); embedding model is local bge-small, not the production
embedding API; pgvector behavior is deferred to a live-DB test.
"""

import json
import re
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from rank_bm25 import BM25Okapi
from selectolax.lexbor import LexborHTMLParser as HTMLParser

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = Path(__file__).parent / "results" / "spike_results.json"

# ---------------------------------------------------------------
# Corpus: real product docs (static HTML sites)
# ---------------------------------------------------------------
PAGES = [
    ("https://docs.astral.sh/uv/concepts/python-versions/", "python-versions"),
    ("https://docs.astral.sh/uv/concepts/projects/", "projects"),
    ("https://docs.astral.sh/uv/concepts/dependencies/", "dependencies"),
    ("https://docs.astral.sh/uv/concepts/resolution/", "resolution"),
    ("https://docs.astral.sh/uv/concepts/cache/", "cache"),
    ("https://docs.astral.sh/uv/concepts/indexes/", "indexes"),
    ("https://docs.astral.sh/uv/concepts/tools/", "tools"),
    ("https://docs.astral.sh/uv/guides/scripts/", "scripts"),
    ("https://docs.astral.sh/uv/guides/projects/", "guide-projects"),
    ("https://docs.astral.sh/uv/guides/tools/", "guide-tools"),
    ("https://docs.astral.sh/uv/guides/integration/docker/", "docker"),
    ("https://docs.astral.sh/uv/pip/compatibility/", "pip-compat"),
    ("https://docs.astral.sh/uv/reference/environment/", "env-vars"),
    ("https://docs.astral.sh/ruff/configuration/", "ruff-config"),
    ("https://docs.astral.sh/ruff/linter/", "ruff-linter"),
    ("https://docs.astral.sh/ruff/formatter/", "ruff-formatter"),
    ("https://docs.astral.sh/ruff/rules/", "ruff-rules"),
    ("https://docs.astral.sh/ruff/settings/", "ruff-settings"),
    ("https://docs.astral.sh/ruff/preview/", "ruff-preview"),
    ("https://docs.astral.sh/ruff/tutorial/", "ruff-tutorial"),
]

# (query, expected page label)
QUERIES = [
    ("how do I pin a specific python version for my project", "python-versions"),
    ("uv keeps downloading a python version I already have", "python-versions"),
    ("where does uv store my project's virtual environment", "projects"),
    ("how do I add a development dependency to my project", "dependencies"),
    ("lockfile keeps changing between machines", "resolution"),
    ("how do I resolve conflicts between package versions", "resolution"),
    ("uv install is slow, can I cache the wheels", "cache"),
    ("how do I clear the uv cache", "cache"),
    ("installing packages from a private package index", "indexes"),
    ("how do I use a custom pypi mirror", "indexes"),
    ("how do I run a one-off tool without installing it", "tools"),
    ("ruff and other tools via uvx", "tools"),
    ("can I put a script with inline dependencies in one file", "scripts"),
    ("how do I run a python file with inline metadata", "scripts"),
    ("how do I create a new project with uv", "guide-projects"),
    ("how do I build and publish my package", "guide-projects"),
    ("how do I install tools globally with uv", "guide-tools"),
    ("how do I dockerize an app that uses uv", "docker"),
    ("uv works locally but fails inside docker build", "docker"),
    ("uv pip commands behave differently than pip", "pip-compat"),
    ("what environment variables does uv respect", "env-vars"),
    ("how do I configure a proxy for uv", "env-vars"),
    ("how do I select which lint rules are enabled", "ruff-config"),
    ("where does ruff read its configuration from", "ruff-config"),
    ("how do I ignore a rule for one line", "ruff-rules"),
    ("ruff says F401 but the import is used", "ruff-rules"),
    ("how do I format my code with ruff", "ruff-formatter"),
    ("how do I enable preview rules", "ruff-preview"),
    ("getting started with ruff in a new project", "ruff-tutorial"),
    ("how do I change the line length for the formatter", "ruff-settings"),
]

STOP = set("the a an and or to of in on for is are i me my we our can you please this that with how do what where why it its as at be by from if not no".split())


def fetch(url: str) -> str | None:
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (spike; miithii de-risk)"},
            timeout=30,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            print(f"  FETCH FAIL {resp.status_code} {url}")
            return None
        return resp.text
    except Exception as exc:  # noqa: BLE001
        print(f"  FETCH FAIL {exc!r} {url}")
        return None


def extract_text(html: str) -> str:
    tree = HTMLParser(html)
    for node in tree.css("nav, header, footer, script, style, aside"):
        node.decompose()
    main = tree.css_first("main") or tree.css_first("article") or tree.body
    text = main.text(separator="\n") if main else tree.text()
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def chunk(text: str, source: str, size: int = 700, overlap: int = 120) -> list[dict]:
    words = text.split()
    out = []
    step = size - overlap
    for i in range(0, len(words), step):
        piece = " ".join(words[i : i + size])
        if len(piece) < 200 and out:
            out[-1]["text"] += " " + piece
            continue
        out.append({"source": source, "text": piece})
        if i + size >= len(words):
            break
    return out


def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9_]+", text.lower()) if w not in STOP and len(w) > 1]


def cosine_top(matrix, query_vec, k):
    sims = matrix @ query_vec
    return np.argsort(-sims)[:k]


def main() -> None:
    import tiktoken
    from fastembed import TextEmbedding

    # ---------- fetch corpus ----------
    pages: dict[str, str] = {}
    print("Fetching corpus...")
    for url, label in PAGES:
        html = fetch(url)
        if html:
            pages[label] = extract_text(html)
            print(f"  ok {label} ({len(pages[label])} chars)")
    fetched = set(pages.keys())

    # ---------- chunk + embed ----------
    chunks: list[dict] = []
    for label, text in pages.items():
        chunks.extend(chunk(text, label))
    print(f"Corpus: {len(pages)} pages, {len(chunks)} chunks")

    print("Loading embedding model (fastembed bge-small-en-v1.5)...")
    t0 = time.perf_counter()
    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    chunk_texts = [c["text"] for c in chunks]
    emb_matrix = np.array(list(model.embed(chunk_texts)))
    emb_matrix = emb_matrix / np.linalg.norm(emb_matrix, axis=1, keepdims=True)
    print(f"Embedded {len(chunks)} chunks in {time.perf_counter()-t0:.1f}s, dim={emb_matrix.shape[1]}")

    # ---------- BM25 ----------
    tokenized = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized)

    def rrf_fuse(q: str, k_rerank: int = 20, k_final: int = 3) -> list[int]:
        qv = next(model.embed([q]))
        qv = qv / np.linalg.norm(qv)
        vec_rank = cosine_top(emb_matrix, qv, k_rerank)
        lex_rank = np.argsort(-bm25.get_scores(tokenize(q)))[:k_rerank]
        scores: dict[int, float] = {}
        for rank, idx in enumerate(vec_rank):
            scores[int(idx)] = scores.get(int(idx), 0.0) + 1.0 / (60 + rank + 1)
        for rank, idx in enumerate(lex_rank):
            scores[int(idx)] = scores.get(int(idx), 0.0) + 1.0 / (60 + rank + 1)
        return [i for i, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:k_final]]

    def top_by(q: str, kind: str, k: int = 3) -> list[int]:
        if kind == "vec":
            qv = next(model.embed([q]))
            qv = qv / np.linalg.norm(qv)
            return list(cosine_top(emb_matrix, qv, k))
        if kind == "bm25":
            return list(np.argsort(-bm25.get_scores(tokenize(q)))[:k])
        return rrf_fuse(q, k_final=k)

    # ---------- score ----------
    print("\nScoring queries...")
    per_method = {m: {"hit1": 0, "hit3": 0, "total": 0} for m in ("vec", "bm25", "hybrid")}
    detail = []
    for query, expected in QUERIES:
        if expected not in fetched:
            detail.append({"query": query, "expected": expected, "skipped": "page not fetched"})
            continue
        row = {"query": query, "expected": expected}
        for method in per_method:
            idxs = top_by(query, method)
            labels = [chunks[i]["source"] for i in idxs]
            hit1 = labels[0] == expected
            hit3 = expected in labels
            per_method[method]["hit1"] += hit1
            per_method[method]["hit3"] += hit3
            per_method[method]["total"] += 1
            row[method] = {"top3": labels, "hit1": hit1, "hit3": hit3}
        detail.append(row)
        marks = " ".join(
            f"{m}:{'Y' if row[m]['hit1'] else ('3' if row[m]['hit3'] else 'N')}" for m in per_method
        )
        print(f"  [{marks}] {query[:60]}")

    print("\n" + "=" * 64)
    print("RETRIEVAL RESULTS (docs.astral.sh corpus, bge-small local embeddings)")
    print("=" * 64)
    for method, s in per_method.items():
        n = s["total"] or 1
        print(f"{method:>6}: hit@1 {s['hit1']}/{s['total']} ({s['hit1']/n:.0%})   hit@3 {s['hit3']}/{s['total']} ({s['hit3']/n:.0%})")

    # ---------- cost model ----------
    enc = tiktoken.get_encoding("cl100k_base")
    sample_tickets = [
        ("short", "I got a 401 when calling the API. I'm using the key from settings. What's wrong?"),
        ("medium", "Our integration stopped working yesterday around 14:00 UTC. Webhooks return 500. "
                   "We haven't changed anything on our side. We're on the Pro plan and this is blocking "
                   "our production sync. Can someone check?"),
        ("long", "Hello, we are evaluating your product for a team of 40 engineers. Since last week our "
                 "CI pipeline fails at the deploy step with a 403 from your API. Retries don't help. "
                 "We tried rotating the key, same result. Logs show the request reaches your edge. "
                 "Our plan is Enterprise with premium support. Please advise whether there is an ongoing "
                 "incident or a change in the authentication requirements, and whether our rate limits "
                 "were reduced after the plan change in March.") * 1,
    ]
    # Prompt overhead: count the ACTUAL supportpilot generation prompt template
    sys.path.insert(0, str(REPO_ROOT / "supportpilot" / "services" / "ai-engine"))
    from app.providers.gemini import GeminiProvider  # noqa: E402
    from app.providers.provider_models import ProviderContext  # noqa: E402
    from app.domain.models import SupportTicket, TicketCategory, TicketSeverity, TicketDifficulty, Action, Customer  # noqa: E402

    probe_ticket = SupportTicket(
        id="T", subject="x", message=sample_tickets[1][1],
        category=TicketCategory.TECHNICAL_API, severity=TicketSeverity.P2,
        difficulty=TicketDifficulty.MEDIUM, customer=Customer(),
        expected_action=Action.ANSWER, expected_answer_summary="",
    )
    ctx = ProviderContext(ticket=probe_ticket, policy_action=Action.ANSWER,
                          policy_flags=[], documents={"doc.md": "x" * 2000})
    prompt = GeminiProvider._build_prompt(object.__new__(GeminiProvider), ctx)  # noqa: SLF001 - spike measurement
    prompt_tokens = len(enc.encode(prompt))
    per_doc_doc_tokens = len(enc.encode("x" * 2000))

    print("\n" + "=" * 64)
    print("COST MODEL (cl100k approximation; verify against Gemini pricing page)")
    print("=" * 64)
    print(f"Fixed prompt overhead (supportpilot template, ~4KB doc): {prompt_tokens} tokens")
    print(f"  -> of which document content: ~{per_doc_doc_tokens} tokens per retrieved doc")
    for name, text in sample_tickets:
        t = len(enc.encode(text))
        total = prompt_tokens + t + 350  # +~350 output tokens per draft
        print(f"{name:>6} ticket: {t} input ticket tokens -> ~{total} tokens/ticket total")

    results = {
        "date": "2026-10-31",
        "corpus": {label: {"url": url, "chars": len(pages.get(label, ""))} for url, label in PAGES},
        "chunks": len(chunks),
        "embedding": "BAAI/bge-small-en-v1.5 via fastembed (local, 384d)",
        "retrieval": {m: {**s, "hit1_pct": s["hit1"] / (s["total"] or 1), "hit3_pct": s["hit3"] / (s["total"] or 1)} for m, s in per_method.items()},
        "detail": detail,
        "cost_model": {
            "tokenizer": "cl100k_base (approximation of Gemini tokenizer)",
            "fixed_prompt_tokens": prompt_tokens,
            "tokens_per_doc_4kb": per_doc_doc_tokens,
            "sample_tickets": {name: len(enc.encode(text)) for name, text in sample_tickets},
        },
        "caveats": [
            "Corpus is a public docs site proxy, not a real tenant help center.",
            "Embeddings are local bge-small, not the production embedding API (Gemini).",
            "Vector store is numpy cosine, not pgvector; pgvector parity is a deferred live-DB test.",
            "Hit-rate labeled against expected page, not against answer faithfulness.",
        ],
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(results, indent=2))
    print(f"\nResults file: {OUT_FILE}")


if __name__ == "__main__":
    main()
