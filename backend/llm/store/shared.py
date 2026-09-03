"""Shared decision store singleton for REVEN.

Provides a single InMemoryDecisionStore instance shared across all
server components (webhook server, LLM API server).

When all components run in the same Python process (e.g., during
development or a single-process deployment), they share one store.

When components run in separate processes, each has its own store
in-memory — acceptable for demo/testing, not production.
"""

from backend.llm.store.decision_store import InMemoryDecisionStore

# Module-level singleton — created once when this module is first imported.
# Subsequent imports return the SAME instance.
_shared_store: InMemoryDecisionStore | None = None


def get_shared_store() -> InMemoryDecisionStore:
    """Get or create the shared decision store singleton.

    Returns:
        The shared InMemoryDecisionStore instance.

    Note:
        When multiple servers run in the same process (e.g., uvicorn workers
        sharing memory via fork), they all reference the same store instance.
        When servers run as separate processes, each has its own store.
    """
    global _shared_store
    if _shared_store is None:
        _shared_store = InMemoryDecisionStore()
    return _shared_store


def reset_shared_store() -> None:
    """Reset the shared store singleton (for testing only).

    Clears all decisions from the shared store and resets the singleton.
    After calling this, get_shared_store() returns a fresh empty store.

    WARNING: Only use in tests. Not safe for production.
    """
    global _shared_store
    _shared_store = InMemoryDecisionStore()
