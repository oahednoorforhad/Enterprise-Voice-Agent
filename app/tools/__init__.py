"""Tool registry.

Each sub-package exposes a flat list of callables that the LLM can
invoke through the orchestrator. The LLM never touches the database
or vector store directly.
"""
