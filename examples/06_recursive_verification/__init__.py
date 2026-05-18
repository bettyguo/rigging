"""Example 06 — recursive verification.

A planner delegates to a worker. The worker's output is audited by a
verifier, whose own verdict envelope is itself audited by a meta-verifier.
Recursion is bounded by ``RigConfig.verification_recursion_cap``.
"""
