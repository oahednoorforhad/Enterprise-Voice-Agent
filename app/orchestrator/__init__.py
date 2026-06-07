"""Orchestrator: drives the per-turn reasoning loop.

Responsibilities:
  1. Receive a normalised user turn from the voice layer.
  2. Run intent analysis.
  3. Select and call tools.
  4. Aggregate evidence and hand it to the reasoning engine.
  5. Stream the final response back to the voice layer.
"""
