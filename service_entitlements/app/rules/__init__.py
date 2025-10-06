"""
Rules engine package.

Defines the rule model and evaluation engine used by the Entitlements
Service. The engine supports composing conditions with different
operators and prioritization, returning a deterministic allow/deny
decision and a rationale for observability.

Modules of interest:
- models: Data classes for Rule, Conditions, Actions, and results.
- engine: Evaluation algorithm with applicability and condition checks.

The engine is designed for in-memory fast evaluation and can be backed
by external persistence for rule storage.
"""
