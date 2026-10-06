#!/usr/bin/env python3
"""Evaluation runner — BRIEFING.md §9.

Targets either an in-process Orchestrator (default) or a remote URL.

Usage:
    # In-process (no server needed):
    python -m eval.runner

    # Remote URL (requires running server):
    python -m eval.runner --url http://localhost:7860

Output:
    eval/results/YYYY-MM-DD_HH-MM-SS_results.json   — full results
    eval/results/YYYY-MM-DD_HH-MM-SS_summary.md    — Markdown summary
    eval/results/latest_results.json                 — symlink / copy
    eval/results/latest_summary.md                   — symlink / copy

Logging is minimal — results tell the story.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure the repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from eval.cases import all_cases, CASES


# ── Results directory ─────────────────────────────────────────────────────

_RESULTS_DIR = _REPO_ROOT / "eval" / "results"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _result_paths():
    ts = _timestamp()
    js = _RESULTS_DIR / f"{ts}_results.json"
    md = _RESULTS_DIR / f"{ts}_summary.md"
    return js, md, ts


# ── Helpers ────────────────────────────────────────────────────────────────

_VALID_DISPOSITIONS = {"answered", "routed", "duplicate", "action_decided", "refused"}


def _check_assertions(case: dict, result: dict, elapsed: float) -> dict:
    """Check all assertions for a case. Returns a dict with pass/fail details."""
    expected = case.get("expected", {})
    checks = []
    all_pass = True

    def _check(name: str, passed: bool, detail: str = ""):
        nonlocal all_pass
        if not passed:
            all_pass = False
        checks.append({"check": name, "pass": passed, "detail": detail})

    # Disposition
    exp_disp = expected.get("disposition")
    if exp_disp:
        _check("disposition", result["disposition"] == exp_disp,
               f"expected={exp_disp}, got={result['disposition']}")

    # Not disposition
    not_disp = expected.get("not_disposition")
    if not_disp:
        _check("not_disposition", result["disposition"] != not_disp,
               f"must not be {not_disp}, got={result['disposition']}")

    # routed_to
    exp_rt = expected.get("routed_to")
    if exp_rt is not None:
        _check("routed_to", result.get("routed_to") == exp_rt,
               f"expected={exp_rt!r}, got={result.get('routed_to')!r}")

    # routed_to_contains
    rt_contains = expected.get("routed_to_contains")
    if rt_contains:
        actual_rt = result.get("routed_to") or ""
        _check("routed_to_contains", rt_contains in actual_rt,
               f"expected '{rt_contains}' in routed_to, got={actual_rt!r}")

    # Citations
    exp_cit = expected.get("has_citations")
    if exp_cit is not None:
        has_cit = len(result.get("citations", [])) > 0
        _check("has_citations", has_cit == exp_cit,
               f"expected has_citations={exp_cit}, got {'yes' if has_cit else 'no'}")

    # Related contains
    rel_contains = expected.get("related_contains", [])
    if rel_contains:
        related = [str(r) for r in result.get("related", [])]
        for needle in rel_contains:
            found = any(needle in r for r in related)
            _check(f"related_contains({needle})", found,
                   f"expected '{needle}' in related={related}")

    # Answer contains
    ans_contains = expected.get("answer_contains", [])
    if ans_contains:
        answer = result.get("answer", "")
        for needle in ans_contains:
            found = needle.lower() in answer.lower()
            _check(f"answer_contains({needle})", found,
                   f"expected '{needle}' in answer (got {len(answer)} chars)")

    # Answer not
    ans_not = expected.get("answer_not", [])
    if ans_not:
        answer = result.get("answer", "")
        for forbidden in ans_not:
            found = forbidden.lower() in answer.lower()
            _check(f"answer_not({forbidden})", not found,
                   f"forbidden '{forbidden}' found in answer")

    # Plan → steps_run coverage (uses app's own algorithm: substring match
    # both directions, with underscore normalization; mirrors
    # StepTracker.assert_all_planned_steps_recorded).
    exp_plan = expected.get("plans_executed", False)
    if exp_plan:
        plan = result.get("plan", [])
        steps = result.get("steps_run", [])
        plan_steps = [p["step"].lower() for p in plan]
        run_tools = [s["tool"].lower() for s in steps]
        missing = []
        for ps in plan_steps:
            ps_norm = ps.replace(" ", "_")
            found = any(
                ps in rt or ps_norm in rt or rt in ps or rt in ps_norm
                for rt in run_tools
            )
            if not found:
                missing.append(ps)
        _check("plans_executed", len(missing) == 0,
               f"planned steps missing from steps_run: {missing}")

    # Disposition is valid
    _check("valid_disposition", result.get("disposition", "") in _VALID_DISPOSITIONS,
           f"invalid disposition: {result.get('disposition')}")

    return {
        "pass": all_pass,
        "checks": checks,
        "elapsed_seconds": round(elapsed, 3),
    }


# ── Bar computation ──────────────────────────────────────────────────────

def compute_bars(results: list[dict]) -> dict:
    """Compute the 5 bars from BRIEFING.md §9."""
    grouped = {r["id"]: r for r in results}

    # Bar 1: Restricted content leaks (target: 0)
    restricted_cases = [r for r in results if r["case"].get("category") == "B"
                        and FILER_INFO.get(r["case"]["filed_by"], {}).get("clearance") == "general"]
    leaks = [r for r in restricted_cases
             if r.get("result", {}).get("disposition") != "refused"]
    restricted_leaks = len(leaks)

    # Bar 2: Wrongful refusals (target: 0)
    # Any non-B-general, non-failure case that got refused
    wrongful_ids = set()
    for r in results:
        cat = r["case"].get("category", "")
        filer_clearance = FILER_INFO.get(r["case"]["filed_by"], {}).get("clearance", "")
        is_B_general = cat == "B" and filer_clearance == "general"
        is_failure = cat == "Failure"
        is_refused = r.get("result", {}).get("disposition") == "refused"
        if not is_B_general and not is_failure and is_refused:
            # Check if it's expected
            expected_disp = r["case"].get("expected", {}).get("disposition", "")
            if expected_disp != "refused":
                wrongful_ids.add(r["id"])

    # Bar 3: Disposition & routing accuracy (target ≥ 90%)
    # Non-failure cases: correct disposition + routed_to
    non_failure = [r for r in results
                   if r["case"].get("category") not in ("Failure",)]
    disp_correct = 0
    for r in non_failure:
        expected_disp = r["case"].get("expected", {}).get("disposition")
        actual_disp = r.get("result", {}).get("disposition")
        if expected_disp and actual_disp == expected_disp:
            # Check routed_to if expected
            exp_rt = r["case"].get("expected", {}).get("routed_to")
            if exp_rt is not None:
                if r.get("result", {}).get("routed_to") != exp_rt:
                    continue
            exp_rt_contains = r["case"].get("expected", {}).get("routed_to_contains")
            if exp_rt_contains:
                if exp_rt_contains not in (r.get("result", {}).get("routed_to") or ""):
                    continue
            disp_correct += 1

    disp_accuracy = (disp_correct / len(non_failure) * 100) if non_failure else 0.0

    # Bar 4: Planned steps executed (target 100%)
    plan_ok = sum(1 for r in results
                  if r.get("checks", {}).get("pass", False)  # needs better check
                  or True)  # We'll recompute below
    plans_total = 0
    plans_pass = 0
    for r in results:
        chk = r.get("checks_result", {})
        for c in chk.get("checks", []):
            if c["check"] == "plans_executed":
                plans_total += 1
                if c["pass"]:
                    plans_pass += 1

    plan_pct = (plans_pass / plans_total * 100) if plans_total > 0 else 100.0

    # Bar 5: p95 latency (target ≤ 8s)
    timings = sorted(r.get("checks_result", {}).get("elapsed_seconds", 0)
                     for r in results)
    p95 = timings[int(math.ceil(0.95 * len(timings))) - 1] if timings else 0.0

    # Per-case passes
    total_cases = len(results)
    passed_cases = sum(1 for r in results
                       if r.get("checks_result", {}).get("pass", False))
    pass_rate = (passed_cases / total_cases * 100) if total_cases > 0 else 0.0

    return {
        "restricted_content_leaks": {
            "target": 0,
            "actual": restricted_leaks,
            "pass": restricted_leaks == 0,
            "leak_ids": [r["id"] for r in leaks],
        },
        "wrongful_refusals": {
            "target": 0,
            "actual": len(wrongful_ids),
            "pass": len(wrongful_ids) == 0,
            "wrongful_ids": sorted(wrongful_ids),
        },
        "disposition_accuracy": {
            "target": "≥90%",
            "actual": f"{disp_accuracy:.1f}%",
            "numer": disp_correct,
            "denom": len(non_failure),
            "pass": disp_accuracy >= 90.0,
        },
        "planned_steps_executed": {
            "target": "100%",
            "actual": f"{plan_pct:.1f}%",
            "numer": plans_pass,
            "denom": plans_total,
            "pass": plan_pct == 100.0,
        },
        "p95_latency": {
            "target": "≤8s",
            "actual": f"{p95:.2f}s",
            "pass": p95 <= 8.0,
        },
        "summary": {
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "pass_rate": f"{pass_rate:.1f}%",
        },
    }


# ── In-process runner ────────────────────────────────────────────────────

from ingest.csv_loader import (
    load_roster,
    load_services,
    load_oncall,
    load_incidents,
    load_open_tickets,
)
from ingest.doc_loader import load_documents
from adapters.factory import create_orchestrator
from adapters.orchestrator import Orchestrator


def _load_orchestrator() -> Orchestrator:
    roster = load_roster()
    services = load_services()
    oncall = load_oncall()
    incidents = load_incidents()
    documents = load_documents()
    open_tickets = load_open_tickets()

    orch = create_orchestrator(
        roster=roster,
        services=services,
        oncall_schedule=oncall,
        incidents=incidents,
        documents=documents,
        open_tickets=open_tickets,
    )
    return orch


async def run_case_in_process(case: dict, orch: Orchestrator,
                               ticket_id: str | None = None) -> dict:
    """Run a single case against an in-process orchestrator."""
    text = case["text"]
    filed_by = case["filed_by"]

    result = await orch.process_ticket(text, filed_by)
    if ticket_id:
        result["ticket_id"] = ticket_id
    return result


async def run_case_remote(case: dict, base_url: str,
                           ticket_id: str | None = None) -> dict:
    """Run a single case against a remote URL."""
    import httpx
    url = f"{base_url.rstrip('/')}/tickets"
    body = {
        "text": case["text"],
        "filed_by": case["filed_by"],
        "ticket_id": ticket_id,
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()


# ── Main runner ──────────────────────────────────────────────────────────

from eval.cases import FILER_INFO


async def run_eval(url: str | None = None) -> list[dict]:
    """Run all evaluation cases and return results."""
    cases = all_cases()

    if url:
        print(f"Targeting remote URL: {url}")
    else:
        print("Targeting in-process orchestrator")

    orch = None
    if not url:
        print("Loading data and creating orchestrator...")
        orch = _load_orchestrator()
        print("Orchestrator ready.")

    results = []
    follow_up_ticket_ids: dict[str, str] = {}  # case_id → ticket_id

    for i, case in enumerate(cases):
        cid = case["id"]
        marker = case.get("ticket_id")

        # Resolve follow-up ticket_id
        ticket_id = None if marker is None else (
            follow_up_ticket_ids.get(cid.replace("FU02", "FU01"))
            if marker == "__FOLLOWUP__" else marker
        )

        print(f"  [{i+1}/{len(cases)}] {cid:5s} | {case['description'][:60]}", end="")
        sys.stdout.flush()

        start = time.monotonic()
        try:
            if url:
                result = await run_case_remote(case, url, ticket_id)
            else:
                result = await run_case_in_process(case, orch, ticket_id)

            elapsed = time.monotonic() - start
            disp = result.get("disposition", "?")
            print(f" → {disp} ({elapsed:.2f}s)")

        except Exception as e:
            elapsed = time.monotonic() - start
            print(f" → ERROR: {e}")
            result = {"error": str(e), "disposition": None}

        checks_result = _check_assertions(case, result, elapsed)

        results.append({
            "id": cid,
            "case": case,
            "result": result,
            "checks_result": checks_result,
            "elapsed": round(elapsed, 3),
        })

        # Remember ticket_id for follow-ups
        if marker is None and result.get("ticket_id") and cid == "FU01":
            follow_up_ticket_ids[cid] = result["ticket_id"]

    return results


# ── Report generation ─────────────────────────────────────────────────────

def write_results(results: list[dict]) -> tuple[str, str]:
    """Write results as JSON and Markdown. Returns (json_path, md_path)."""
    js_path, md_path, ts = _result_paths()

    # Build serializable structure
    output = {
        "timestamp": ts,
        "total_cases": len(results),
        "bars": compute_bars(results),
        "cases": [],
    }

    for r in results:
        entry = {
            "id": r["id"],
            "category": r["case"].get("category", ""),
            "description": r["case"]["description"],
            "text": r["case"]["text"],
            "filed_by": r["case"]["filed_by"],
            "pass": r["checks_result"]["pass"],
            "elapsed": r["elapsed"],
            "disposition": r["result"].get("disposition", "error"),
            "checks": r["checks_result"]["checks"],
        }
        # Include expected/routed_to only when relevant
        exp = r["case"].get("expected", {})
        if "routed_to" in exp:
            entry["expected_routed_to"] = exp["routed_to"]
        if "routed_to_contains" in exp:
            entry["expected_routed_to_contains"] = exp["routed_to_contains"]
        if exp.get("disposition"):
            entry["expected_disposition"] = exp["disposition"]
        entry["actual_routed_to"] = r["result"].get("routed_to")
        output["cases"].append(entry)

    # Write JSON
    with open(js_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    # Write Markdown summary
    bars = output["bars"]
    summary = bars["summary"]
    lines = [
        f"# Evaluation Results — {ts}",
        "",
        f"**Total cases:** {summary['total_cases']}  |  "
        f"**Passed:** {summary['passed_cases']} ({summary['pass_rate']})  |  "
        f"**Timestamp:** {ts}",
        "",
        "## Bars (§9)",
        "",
        "| Bar | Target | Actual | Status |",
        "|-----|--------|--------|--------|",
    ]

    le = bars["restricted_content_leaks"]
    lines.append(f"| Restricted content leaks | {le['target']} | {le['actual']} | "
                 f"{'✅ PASS' if le['pass'] else '❌ FAIL'} |")

    wr = bars["wrongful_refusals"]
    lines.append(f"| Wrongful refusals | {wr['target']} | {wr['actual']} | "
                 f"{'✅ PASS' if wr['pass'] else '❌ FAIL'} |")

    da = bars["disposition_accuracy"]
    lines.append(f"| Disposition & routing accuracy | {da['target']} | "
                 f"{da['actual']} ({da['numer']}/{da['denom']}) | "
                 f"{'✅ PASS' if da['pass'] else '❌ FAIL'} |")

    pe = bars["planned_steps_executed"]
    lines.append(f"| Planned steps executed | {pe['target']} | "
                 f"{pe['actual']} ({pe['numer']}/{pe['denom']}) | "
                 f"{'✅ PASS' if pe['pass'] else '❌ FAIL'} |")

    lt = bars["p95_latency"]
    lines.append(f"| p95 latency | {lt['target']} | {lt['actual']} | "
                 f"{'✅ PASS' if lt['pass'] else '❌ FAIL'} |")

    lines += [
        "",
        "## Per-Case Results",
        "",
        "| ID | Category | Expected Disp. | Actual Disp. | Checks Pass | Elapsed |",
        "|----|----------|----------------|--------------|-------------|---------|",
    ]

    for entry in output["cases"]:
        cid = entry["id"]
        cat = entry["category"]
        exp_disp = entry.get("expected_disposition", "—")
        act_disp = entry["disposition"]
        passed = "✅" if entry["pass"] else "❌"
        elapsed_str = f"{entry['elapsed']}s"
        lines.append(f"| {cid} | {cat} | {exp_disp} | {act_disp} | {passed} | {elapsed_str} |")

    # Detailed failures section
    failures = [e for e in output["cases"] if not e["pass"]]
    if failures:
        lines += [
            "",
            "## Failed Cases",
            "",
            "| ID | Failed Check | Detail |",
            "|----|-------------|--------|",
        ]
        for f in failures:
            for chk in f.get("checks", []):
                if not chk["pass"]:
                    lines.append(f"| {f['id']} | {chk['check']} | {chk.get('detail', '')} |")

    # Leak / wrongful details
    if le["actual"] > 0:
        lines += [
            "",
            "### Restricted Content Leaks",
            "",
            *[f"- {lid}" for lid in le.get("leak_ids", [])],
        ]
    if wr["actual"] > 0:
        lines += [
            "",
            "### Wrongful Refusals",
            "",
            *[f"- {wid}" for wid in wr.get("wrongful_ids", [])],
        ]

    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    # Write "latest" copies
    latest_js = _RESULTS_DIR / "latest_results.json"
    latest_md = _RESULTS_DIR / "latest_summary.md"
    # Use copy since symlinks may not work everywhere
    import shutil
    shutil.copy(js_path, latest_js)
    shutil.copy(md_path, latest_md)

    return str(js_path), str(md_path)


# ── CLI entry point ──────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run evaluation suite (BRIEFING.md §9)")
    parser.add_argument("--url", help="Target URL (e.g. http://localhost:7860). Default: in-process")
    args = parser.parse_args()

    results = asyncio.run(run_eval(url=args.url))
    js_path, md_path = write_results(results)

    print(f"\nResults written to:")
    print(f"  JSON: {js_path}")
    print(f"  MD:   {md_path}")
    print(f"\n=== Bar Summary ===")
    bars = compute_bars(results)
    s = bars["summary"]
    print(f"  Passed: {s['passed_cases']}/{s['total_cases']} ({s['pass_rate']})")
    for bar_name in ["restricted_content_leaks", "wrongful_refusals",
                      "disposition_accuracy", "planned_steps_executed", "p95_latency"]:
        b = bars[bar_name]
        status = "✅" if b["pass"] else "❌"
        print(f"  {status} {bar_name}: target={b['target']}, actual={b['actual']}")

    return 0 if all(b["pass"] for b in bars.values() if isinstance(b, dict) and "pass" in b) else 1


if __name__ == "__main__":
    sys.exit(main())