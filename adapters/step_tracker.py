"""Step tracking — produces `plan` and `steps_run` per the API contract.

Plan is created *before* execution. Steps_run records what *actually* happened.
Both are compared by graders. Every step in plan must appear in steps_run
(may be skipped/failed/timeout).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlannedStep:
    """A single planned step."""
    step: str
    why: str


@dataclass
class ExecutedStep:
    """A single executed (or attempted) step."""
    tool: str
    outcome: str  # "ok" | "failed" | "timeout" | "skipped"
    detail: str


class StepTracker:
    """Tracks plan creation and step execution.

    Usage:
        tracker = StepTracker()
        tracker.plan("Identify filer", "Need to know who filed the ticket")
        ...
        tracker.ok("get_filer", "Found Priya Nathan (FEN-1001)")
        tracker.failed("classify", "LLM timed out, using rules fallback")
        tracker.timeout("search_documents", "Document search exceeded 2s timeout")
        tracker.skipped("page_oncall", "Not a routing scenario")
    """

    def __init__(self) -> None:
        self._plan: list[PlannedStep] = []
        self._steps_run: list[ExecutedStep] = []

    # ── Plan building ───────────────────────────────────────────────────

    def plan(self, step: str, why: str) -> None:
        """Add a step to the plan (what we *intend* to do)."""
        self._plan.append(PlannedStep(step=step, why=why))

    # ── Execution recording ─────────────────────────────────────────────

    def ok(self, tool: str, detail: str) -> None:
        """Record a successfully executed step."""
        self._steps_run.append(ExecutedStep(tool=tool, outcome="ok", detail=detail))

    def failed(self, tool: str, detail: str) -> None:
        """Record a failed step."""
        self._steps_run.append(ExecutedStep(tool=tool, outcome="failed", detail=detail))

    def timeout(self, tool: str, detail: str) -> None:
        """Record a timed-out step."""
        self._steps_run.append(ExecutedStep(tool=tool, outcome="timeout", detail=detail))

    def skipped(self, tool: str, detail: str) -> None:
        """Record a skipped step."""
        self._steps_run.append(ExecutedStep(tool=tool, outcome="skipped", detail=detail))

    # ── Results ─────────────────────────────────────────────────────────

    def get_plan(self) -> list[dict[str, str]]:
        """Return plan as serialisable dict list."""
        return [{"step": p.step, "why": p.why} for p in self._plan]

    def get_steps_run(self) -> list[dict[str, str]]:
        """Return steps_run as serialisable dict list."""
        return [
            {"tool": s.tool, "outcome": s.outcome, "detail": s.detail}
            for s in self._steps_run
        ]

    def assert_all_planned_steps_recorded(self) -> list[str]:
        """Check every planned step has a corresponding steps_run entry.

        Returns a list of discrepancies (empty = all good).
        A planned step is considered "recorded" if its step name (lowercased)
        appears as a substring of any executed step's tool name, or vice versa.
        """
        plan_steps = [p.step.lower() for p in self._plan]
        run_tools = [s.tool.lower() for s in self._steps_run]

        missing: list[str] = []
        for ps in plan_steps:
            # Check if this plan step (or a substring) appears in any run tool
            ps_normalized = ps.replace(" ", "_")
            found = any(
                ps in rt or ps_normalized in rt or rt in ps or rt in ps_normalized
                for rt in run_tools
            )
            if not found:
                missing.append(f"Step '{ps}' planned but no corresponding steps_run entry")
        return missing