"""Rule-based fallback classification when the model fails/times out.

This module re-exports the rule-based classifier from classify.py
so the orchestrator can import a single entry point.
"""

from classify.classify import classify, extract_services, extract_action_request

rules_classify = classify
match_keywords = extract_services