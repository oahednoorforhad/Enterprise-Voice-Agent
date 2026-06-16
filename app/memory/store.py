"""Per-customer conversational memory store.

Maintains recent turn history (user message → assistant response) in
memory, keyed by customer ID.  History is truncated to the most recent
``max_turns`` exchanges to keep prompt sizes bounded.
"""

from __future__ import annotations


class ConversationMemory:
    """Simple in-memory conversation history per customer.

    Parameters
    ----------
    max_turns:
        Maximum number of past (user, assistant) pairs to retain per
        customer.  Older turns are dropped.  Defaults to 10.
    """

    def __init__(self, max_turns: int = 10) -> None:
        self._max_turns = max_turns
        self._store: dict[str, list[dict[str, str]]] = {}

    def add_turn(
        self,
        customer_id: str,
        user_message: str,
        assistant_response: str,
    ) -> None:
        """Record one completed turn for *customer_id*."""
        if customer_id not in self._store:
            self._store[customer_id] = []
        self._store[customer_id].append({
            "user": user_message,
            "assistant": assistant_response,
        })
        # Keep only the most recent N turns
        if len(self._store[customer_id]) > self._max_turns:
            self._store[customer_id] = self._store[customer_id][-self._max_turns:]

    def get_history(self, customer_id: str) -> list[dict[str, str]]:
        """Return all stored turns for *customer_id* (empty list if none)."""
        return self._store.get(customer_id, [])

    def format_prompt_context(self, customer_id: str) -> str:
        """Return prior turns as a readable block for injection into prompts.

        Because :meth:`add_turn` is called *after* a turn is processed,
        every entry in the history list is already a completed prior turn
        (never the current in-flight turn).  Returns an empty string when
        there is no prior conversation.
        """
        history = self.get_history(customer_id)
        if not history:
            return ""

        lines = ["--- Prior conversation ---"]
        for i, turn in enumerate(history, start=1):
            lines.append(f"Turn {i}:")
            lines.append(f"  Customer: {turn['user']}")
            lines.append(f"  EVA:      {turn['assistant']}")
        lines.append("--- End of prior conversation ---\n")
        return "\n".join(lines)
