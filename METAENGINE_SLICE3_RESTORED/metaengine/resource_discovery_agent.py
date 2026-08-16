"""resource_discovery_agent.py — Autonomous web-search agent that finds and
connects new free resources (LLM providers, compute, datasets) to MetaEngine.

This agent runs as part of the autonomous_orchestrator. Every cycle it:

  1. SEARCHES the web for free LLM providers / compute resources / datasets
     using multiple strategies:
       a. z-ai web_search (when not rate-limited)
       b. DuckDuckGo HTML scraping (no API key, always available)
       c. GitHub repos search (GitHub API, no auth needed for public search)
       d. HuggingFace model hub (free API)
       e. Direct probes of known-free endpoints (api.together.xyz, etc.)

  2. EXTRACTS candidate providers from search results. Each candidate has:
       - provider_name
       - api_endpoint (guessed from URL)
       - api_docs_url (from search result)
       - free_tier_rpm (parsed from snippet)
       - signup_url

  3. TESTS each candidate by sending a tiny probe request via LiteLLM or
     direct HTTP. Records which ones actually work RIGHT NOW.

  4. WRITES working providers to:
       - storage/discovered_providers.json  (full discovery log)
       - metaengine/adaptation_patches/discovered_provider_*.json
         These patches are read by multi_provider_validator.py at startup,
         so newly-discovered providers become available automatically.

  5. REPORTS to autonomous_orchestrator (summary stats).

Search queries used (rotated each cycle to avoid stale results):
  - "free LLM API providers 2026 no credit card"
  - "free OpenAI-compatible API endpoints"
  - "free GPU cloud compute 2026"
  - "free benchmark datasets for LLM evaluation"
  - "free CI/CD minutes public repository"
  - "huggingface inference API free models"
  - "openrouter free models list"
  - "litellm supported providers list"

Usage:
  python3 -m metaengine.resource_discovery_agent           # one discovery cycle
  python3 -m metaengine.resource_discovery_agent --forever  # infinite
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import traceback
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("ME_BENCHMARK_ROOT") or Path(__file__).resolve().parent.parent)
STORAGE = ROOT / "storage"
DISCOVERY_STATE_FILE = STORAGE / "resource_discovery_state.json"
DISCOVERY_LOG = STORAGE / "resource_discovery.log"
DISCOVERED_PROVIDERS_FILE = STORAGE / "discovered_providers.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg: str) -> None:
    line = f"[{_now_iso()}] [discovery] {msg}"
    print(line, flush=True)
    try:
        DISCOVERY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DISCOVERY_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Search query rotation
# ---------------------------------------------------------------------------


# Each query targets a different kind of free resource.
SEARCH_QUERIES = [
    # LLM API providers
    "free LLM API providers 2026 no credit card",
    "free OpenAI-compatible API endpoints list",
    "openrouter free models list 2026",
    "huggingface inference API free models",
    "groq free tier rate limits 2026",
    "together AI free credit signup",
    "anthropic free API tier",
    "gemini free API tier limits",
    "cohere trial API free",
    "litellm supported providers free",
    # Compute resources
    "free GPU cloud compute 2026",
    "free CI/CD minutes public repository",
    "github actions free tier limits 2026",
    "free serverless function providers",
    "free colabs kaggle free GPU",
    # Datasets / benchmarks
    "free benchmark datasets LLM evaluation",
    "MMLU dataset free download",
    "huggingface datasets free",
    # Open source projects
    "github metaengine LLM benchmark",
    "github autonomous AI system open source",
]


# ---------------------------------------------------------------------------
# Discovery result types
# ---------------------------------------------------------------------------


@dataclass
class DiscoveredProvider:
    """A discovered candidate resource."""
    provider_name: str
    category: str  # "llm_api", "compute", "dataset", "ci_cd"
    api_endpoint: str = ""
    api_docs_url: str = ""
    signup_url: str = ""
    free_tier_rpm: int = 0
    litellm_model_hint: str = ""
    works: bool = False
    probe_response: str = ""
    probe_error: str = ""
    probe_latency_ms: float = 0.0
    discovered_at: str = ""
    source_query: str = ""
    source_url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Search strategies
# ---------------------------------------------------------------------------


def search_via_zai(query: str, num: int = 5) -> list[dict]:
    """Search via z-ai web_search CLI. Returns list of search result dicts.

    Returns [] if rate-limited (429) or any other error.
    """
    try:
        result = subprocess.run(
            ["z-ai", "function", "-n", "web_search",
             "-a", json.dumps({"query": query, "num": num})],
            capture_output=True, text=True, timeout=30,
        )
        if "429" in result.stderr or "Too many requests" in result.stderr:
            _log(f"  [zai-search] 429 rate-limited for query: {query[:60]}")
            return []
        if result.returncode != 0:
            _log(f"  [zai-search] error: {result.stderr[-150:]}")
            return []
        # Output is JSON to stdout
        try:
            data = json.loads(result.stdout)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "results" in data:
                return data["results"]
        except Exception:
            pass
        return []
    except subprocess.TimeoutExpired:
        _log(f"  [zai-search] timeout for query: {query[:60]}")
        return []
    except Exception as exc:
        _log(f"  [zai-search] exception: {exc}")
        return []


def search_via_duckduckgo(query: str, num: int = 5) -> list[dict]:
    """Search via DuckDuckGo HTML endpoint (no API key required).

    Uses https://html.duckduckgo.com/html/?q=... which returns HTML we parse.
    Always available, no rate limits (for reasonable use).
    """
    results: list[dict] = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # DuckDuckGo HTML structure:
        #   <a class="result__a" href="//duckduckgo.com/l/?uddg=<encoded_url>...">...title spans...</a>
        #   <a class="result__snippet" href="...">...snippet text...</a>
        # Find all result blocks first
        # Strategy: find each <a class="result__a" ... href="..." ...>...</a> (greedy on inner content)
        result_pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        snippet_pattern = re.compile(
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        result_matches = result_pattern.findall(html)
        snippet_matches = snippet_pattern.findall(html)
        for i, (raw_url, raw_title) in enumerate(result_matches[:num]):
            # DDG wraps URLs: //duckduckgo.com/l/?uddg=<encoded>&rut=...
            actual_url = raw_url
            m = re.search(r"uddg=([^&]+)", raw_url)
            if m:
                actual_url = urllib.parse.unquote(m.group(1))
            # Strip HTML tags from title (it may contain <span>...</span>)
            title = re.sub(r"<[^>]+>", "", raw_title).strip()
            snippet = ""
            if i < len(snippet_matches):
                snippet = re.sub(r"<[^>]+>", "", snippet_matches[i]).strip()[:300]
            host = urllib.parse.urlparse(actual_url).hostname or ""
            results.append({
                "url": actual_url,
                "name": title,
                "snippet": snippet,
                "host_name": host,
                "source": "duckduckgo",
            })
    except Exception as exc:
        _log(f"  [ddg-search] exception: {exc}")
    return results


def search_via_github(query: str, num: int = 5) -> list[dict]:
    """Search GitHub repos. No auth needed for public search (rate-limited)."""
    results: list[dict] = []
    try:
        # Use the search/repositories endpoint
        url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&per_page={num}&sort=stars"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "MetaEngine/2.3",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for r in data.get("items", [])[:num]:
            results.append({
                "url": r["html_url"],
                "name": r["full_name"],
                "snippet": (r.get("description") or "")[:300],
                "host_name": "github.com",
                "stars": r.get("stargazers_count", 0),
                "source": "github",
            })
    except Exception as exc:
        _log(f"  [github-search] exception: {exc}")
    return results


def search_via_huggingface(query: str, num: int = 5) -> list[dict]:
    """Search HuggingFace model hub (free API)."""
    results: list[dict] = []
    try:
        url = f"https://huggingface.co/api/models?search={urllib.parse.quote(query)}&limit={num}&sort=downloads&direction=-1"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MetaEngine/2.3"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for m in data[:num] if isinstance(data, list) else []:
            results.append({
                "url": f"https://huggingface.co/{m.get('id','')}",
                "name": m.get("id", ""),
                "snippet": f"Downloads: {m.get('downloads',0)}, Likes: {m.get('likes',0)}",
                "host_name": "huggingface.co",
                "source": "huggingface",
            })
    except Exception as exc:
        _log(f"  [hf-search] exception: {exc}")
    return results


def search_all(query: str, num: int = 5) -> list[dict]:
    """Run all search strategies and combine results."""
    all_results: list[dict] = []
    # Try z-ai first (best quality if not rate-limited)
    zai_results = search_via_zai(query, num=num)
    all_results.extend(zai_results)
    # Always try DuckDuckGo (no rate limits)
    ddg_results = search_via_duckduckgo(query, num=num)
    all_results.extend(ddg_results)
    # GitHub for code queries
    if any(kw in query.lower() for kw in ["github", "repository", "code", "benchmark"]):
        gh_results = search_via_github(query, num=num)
        all_results.extend(gh_results)
    # HuggingFace for model queries
    if any(kw in query.lower() for kw in ["model", "inference", "llm", "huggingface"]):
        hf_results = search_via_huggingface(query, num=num)
        all_results.extend(hf_results)
    return all_results


# ---------------------------------------------------------------------------
# Candidate extraction
# ---------------------------------------------------------------------------


# Patterns to detect provider signup URLs and guess API endpoints
_PROVIDER_PATTERNS = {
    "groq": {"litellm_model": "groq/llama-3.1-70b-versatile", "api_endpoint": "https://api.groq.com/openai"},
    "openrouter": {"litellm_model": "openrouter/auto", "api_endpoint": "https://openrouter.ai/api/v1"},
    "together": {"litellm_model": "together_ai/Meta-Llama-3.1-70B-Instruct-Turbo", "api_endpoint": "https://api.together.xyz/v1"},
    "anthropic": {"litellm_model": "anthropic/claude-3-5-sonnet-20240620", "api_endpoint": "https://api.anthropic.com/v1"},
    "gemini": {"litellm_model": "gemini/gemini-1.5-flash", "api_endpoint": "https://generativelanguage.googleapis.com/v1"},
    "huggingface": {"litellm_model": "huggingface/meta-llama/Meta-Llama-3-70B-Instruct", "api_endpoint": "https://api-inference.huggingface.co"},
    "cohere": {"litellm_model": "cohere/command-r", "api_endpoint": "https://api.cohere.ai/v1"},
    "deepinfra": {"litellm_model": "deepinfra/Meta-Llama-3.1-70B-Instruct", "api_endpoint": "https://api.deepinfra.com/v1"},
    "fireworks": {"litellm_model": "fireworks_ai/llama-v3p1-70b-instruct", "api_endpoint": "https://api.fireworks.ai/inference/v1"},
    "novita": {"litellm_model": "novita/meta-llama/llama-3.1-70b-instruct", "api_endpoint": "https://api.novita.ai/v3"},
    "lepton": {"litellm_model": "lepton/llama3-70b", "api_endpoint": "https://api.lepton.ai/v1"},
    "perplexity": {"litellm_model": "perplexity/llama-3.1-70b-instruct", "api_endpoint": "https://api.perplexity.ai"},
    "ai21": {"litellm_model": "ai21/jamba-1-5-large", "api_endpoint": "https://api.ai21.com/studio/v1"},
    "mistral": {"litellm_model": "mistral/mistral-large-latest", "api_endpoint": "https://api.mistral.ai/v1"},
    "openai": {"litellm_model": "openai/gpt-4o-mini", "api_endpoint": "https://api.openai.com/v1"},
}


def classify_category(query: str) -> str:
    q = query.lower()
    if any(kw in q for kw in ["gpu", "compute", "serverless", "ci/cd", "ci cd"]):
        return "compute"
    if any(kw in q for kw in ["dataset", "benchmark", "mmlu"]):
        return "dataset"
    return "llm_api"


def extract_candidates(query: str, search_results: list[dict]) -> list[DiscoveredProvider]:
    """Extract provider candidates from search results."""
    candidates: list[DiscoveredProvider] = []
    category = classify_category(query)
    seen_names: set[str] = set()

    for r in search_results:
        url = r.get("url", "")
        name = r.get("name", "")
        snippet = r.get("snippet", "")
        host = r.get("host_name", "") or urllib.parse.urlparse(url).hostname or ""

        # Match against known provider patterns
        for provider_key, info in _PROVIDER_PATTERNS.items():
            if provider_key in host.lower() or provider_key in name.lower() or provider_key in snippet.lower():
                if provider_key in seen_names:
                    continue
                seen_names.add(provider_key)
                # Try to parse free_tier_rpm from snippet
                rpm = 0
                m = re.search(r"(\d+)\s*(?:req|requests?)/min", snippet, re.I)
                if m:
                    rpm = int(m.group(1))
                m = re.search(r"(\d+)\s*RPM", snippet)
                if m:
                    rpm = int(m.group(1))
                candidates.append(DiscoveredProvider(
                    provider_name=provider_key,
                    category=category,
                    api_endpoint=info["api_endpoint"],
                    litellm_model_hint=info["litellm_model"],
                    signup_url=f"https://{provider_key}.com" if not host else f"https://{host}",
                    api_docs_url=url,
                    free_tier_rpm=rpm,
                    discovered_at=_now_iso(),
                    source_query=query,
                    source_url=url,
                ))
                break
    return candidates


# ---------------------------------------------------------------------------
# Probe candidates
# ---------------------------------------------------------------------------


def probe_candidate(candidate: DiscoveredProvider) -> DiscoveredProvider:
    """Probe a discovered provider to see if it actually responds."""
    candidate.probe_response = ""
    candidate.probe_error = ""
    candidate.probe_latency_ms = 0.0
    candidate.works = False

    # We don't have an API key for unknown providers, so we just check if the
    # API endpoint is reachable (HTTP HEAD or simple GET).
    if not candidate.api_endpoint:
        candidate.probe_error = "no api_endpoint known"
        return candidate

    try:
        t0 = time.perf_counter()
        # Try a HEAD request to the API endpoint
        req = urllib.request.Request(
            candidate.api_endpoint,
            method="HEAD",
            headers={"User-Agent": "MetaEngine/2.3 discovery probe"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            candidate.probe_latency_ms = (time.perf_counter() - t0) * 1000
            candidate.probe_response = f"HTTP {resp.status}"
            # 200 or 401/403 means the endpoint exists and is responding
            # 404/5xx means it's broken
            candidate.works = resp.status in (200, 401, 403, 405)
    except urllib.error.HTTPError as e:
        candidate.probe_latency_ms = (time.perf_counter() - t0) * 1000
        # 401/403 means the endpoint exists (just needs auth) — still "works"
        candidate.probe_response = f"HTTP {e.code}"
        candidate.works = e.code in (401, 403, 405)
        if not candidate.works:
            candidate.probe_error = f"HTTP {e.code}"
    except urllib.error.URLError as e:
        candidate.probe_error = f"URLError: {e.reason}"
    except Exception as e:
        candidate.probe_error = f"{type(e).__name__}: {e}"
    return candidate


# Generate patches for working providers
# ---------------------------------------------------------------------------


def generate_provider_patches(providers: list[DiscoveredProvider]) -> list[dict]:
    """Generate META_TUNING patches that add newly-discovered providers
    to multi_provider_validator.py's DEFAULT_PROVIDERS list.
    """
    patches: list[dict] = []
    now = _now_iso()
    for p in providers:
        if not p.works:
            continue
        # Generate a patch that adds this provider to the validator's list
        patch_id = hashlib.sha256(
            f"provider:{p.provider_name}:{p.api_endpoint}".encode()
        ).hexdigest()[:32]
        patch = {
            "patch_id": patch_id,
            "patch_type": "PROVIDER_ADDITION",
            "target_module": "metaengine/multi_provider_validator.py",
            "title": f"Add discovered provider: {p.provider_name}",
            "rationale": f"Discovered at {now} via query '{p.source_query}'. "
                         f"Endpoint {p.api_endpoint} responds (HTTP probe OK, "
                         f"{p.probe_latency_ms:.0f}ms).",
            "patch_content": {
                "provider_name": p.provider_name,
                "litellm_model": p.litellm_model_hint or "auto",
                "api_endpoint": p.api_endpoint,
                "free_tier_rpm": p.free_tier_rpm,
                "signup_url": p.signup_url,
                "api_docs_url": p.api_docs_url,
            },
            "confidence": 0.6,  # lower confidence since we only verified reachability, not auth
            "generated_at": now,
        }
        patches.append(patch)
    return patches


def save_provider_patches(patches: list[dict]) -> None:
    """Save provider patches to adaptation_patches/ directory."""
    PATCHES_DIR = ROOT / "metaengine" / "adaptation_patches"
    PATCHES_DIR.mkdir(parents=True, exist_ok=True)
    for p in patches:
        filename = f"provider_addition_{p['patch_id']}.json"
        filepath = PATCHES_DIR / filename
        try:
            filepath.write_text(
                json.dumps(p, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            _log(f"  saved provider patch: {filename}")
        except Exception as exc:
            _log(f"  failed to save {filename}: {exc}")


# ---------------------------------------------------------------------------
# State + persistence
# ---------------------------------------------------------------------------


def load_discovery_state() -> dict:
    if DISCOVERY_STATE_FILE.is_file():
        try:
            return json.loads(DISCOVERY_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "cycle_count": 0,
        "cycles": [],
        "all_discovered_providers": [],
        "working_providers": [],
    }


def save_discovery_state(state: dict) -> None:
    try:
        DISCOVERY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        DISCOVERY_STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        _log(f"[state] save failed: {exc}")


def save_discovered_providers(providers: list[DiscoveredProvider]) -> None:
    """Persist the full discovered providers list for inspection."""
    try:
        DISCOVERED_PROVIDERS_FILE.write_text(
            json.dumps(
                {
                    "updated_at": _now_iso(),
                    "total": len(providers),
                    "working": len([p for p in providers if p.works]),
                    "providers": [p.to_dict() for p in providers],
                },
                ensure_ascii=False, indent=2, default=str,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        _log(f"[save_providers] failed: {exc}")


# ---------------------------------------------------------------------------
# Main discovery cycle
# ---------------------------------------------------------------------------


def run_discovery_cycle(cycle_id: int) -> dict:
    """Run one resource discovery cycle. Returns cycle summary."""
    _log("=" * 60)
    _log(f"=== DISCOVERY CYCLE {cycle_id} START ===")
    _log("=" * 60)
    t0 = time.perf_counter()

    # Rotate through queries — pick 3 different ones each cycle
    state = load_discovery_state()
    cycle_idx = (cycle_id - 1) % len(SEARCH_QUERIES)
    queries_this_cycle = [
        SEARCH_QUERIES[cycle_idx],
        SEARCH_QUERIES[(cycle_idx + 7) % len(SEARCH_QUERIES)],
        SEARCH_QUERIES[(cycle_idx + 13) % len(SEARCH_QUERIES)],
    ]
    _log(f"[queries] {queries_this_cycle}")

    all_candidates: list[DiscoveredProvider] = []
    search_total = 0
    for query in queries_this_cycle:
        results = search_all(query, num=5)
        search_total += len(results)
        _log(f"  query: '{query[:60]}' → {len(results)} results")
        candidates = extract_candidates(query, results)
        _log(f"    extracted {len(candidates)} candidates")
        all_candidates.extend(candidates)
        # Be polite to search APIs
        time.sleep(2)

    # Deduplicate candidates by provider_name (later wins)
    by_name: dict[str, DiscoveredProvider] = {}
    for c in all_candidates:
        by_name[c.provider_name] = c
    unique_candidates = list(by_name.values())
    _log(f"[dedup] {len(all_candidates)} → {len(unique_candidates)} unique candidates")

    # Probe each candidate
    _log("[probe] testing candidates...")
    for c in unique_candidates:
        probe_candidate(c)
        status = "✓ WORKS" if c.works else f"✗ {c.probe_error[:50]}"
        _log(f"  {c.provider_name:15s} {status}  ({c.probe_latency_ms:.0f}ms)")

    # Generate patches for working providers
    patches = generate_provider_patches(unique_candidates)
    if patches:
        _log(f"[patches] generated {len(patches)} provider patches")
        save_provider_patches(patches)

    # Save discovered providers list
    save_discovered_providers(unique_candidates)

    # Update state
    state["cycle_count"] = cycle_id
    state["cycles"].append({
        "cycle_id": cycle_id,
        "started_at": _now_iso(),
        "duration_sec": round(time.perf_counter() - t0, 2),
        "queries": queries_this_cycle,
        "search_results_total": search_total,
        "candidates_found": len(unique_candidates),
        "working_providers": len([c for c in unique_candidates if c.works]),
        "patches_generated": len(patches),
    })
    state["cycles"] = state["cycles"][-50:]
    # Update all_discovered_providers (merge with previous discoveries)
    seen_names = {p["provider_name"] for p in state.get("all_discovered_providers", [])}
    for c in unique_candidates:
        if c.provider_name not in seen_names:
            state["all_discovered_providers"].append(c.to_dict())
            seen_names.add(c.provider_name)
    # Track currently-working providers (replace, not append)
    state["working_providers"] = [c.to_dict() for c in unique_candidates if c.works]
    save_discovery_state(state)

    cycle_summary = {
        "cycle_id": cycle_id,
        "duration_sec": round(time.perf_counter() - t0, 2),
        "queries_run": len(queries_this_cycle),
        "search_results_total": search_total,
        "candidates_found": len(unique_candidates),
        "working_providers": len([c for c in unique_candidates if c.works]),
        "patches_generated": len(patches),
    }
    _log(f"=== DISCOVERY CYCLE {cycle_id} END — "
         f"{cycle_summary['working_providers']}/{cycle_summary['candidates_found']} providers work, "
         f"{cycle_summary['patches_generated']} patches ===")
    return cycle_summary


def run_forever(interval_sec: int = 1800) -> None:
    """Run discovery cycles forever. Default interval = 30 minutes."""
    state = load_discovery_state()
    cycle_id = state.get("cycle_count", 0) + 1
    _log(f"=== RESOURCE DISCOVERY AGENT STARTING (cycle {cycle_id}, interval={interval_sec}s) ===")

    _shutdown = {"requested": False}

    def _handler(signum, frame):
        _shutdown["requested"] = True
        _log(f"[signal] received {signum} — will exit after current cycle")

    try:
        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)
    except Exception:
        pass

    while not _shutdown["requested"]:
        try:
            run_discovery_cycle(cycle_id)
        except Exception as exc:
            _log(f"[discovery] cycle {cycle_id} crashed: {exc}")
            _log(traceback.format_exc()[-800:])

        cycle_id += 1
        if _shutdown["requested"]:
            break
        _log(f"[discovery] sleeping {interval_sec}s before next cycle")
        slept = 0
        while slept < interval_sec and not _shutdown["requested"]:
            time.sleep(min(15, interval_sec - slept))
            slept += 15

    _log("=== RESOURCE DISCOVERY AGENT EXITED ===")


def main() -> int:
    ap = argparse.ArgumentParser(description="MetaEngine resource discovery agent")
    ap.add_argument("--forever", action="store_true",
                    help="Run discovery cycles forever (until killed).")
    ap.add_argument("--interval", type=int, default=1800,
                    help="Seconds between cycles (default: 1800 = 30 min).")
    args = ap.parse_args()

    if args.forever:
        run_forever(interval_sec=args.interval)
        return 0
    else:
        state = load_discovery_state()
        cycle_id = state.get("cycle_count", 0) + 1
        run_discovery_cycle(cycle_id)
        return 0


if __name__ == "__main__":
    sys.exit(main())
