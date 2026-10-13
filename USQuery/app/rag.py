"""Retrieval-augmented generation for bill chat.

The implementation is not included in this public snapshot. These stubs keep
the same interface so the rest of the application imports and runs.
"""

from typing import List


async def index_bill(bill) -> bool:
    """Index a bill's documents for retrieval. Not included; no-op."""
    return False


async def retrieve_relevant_chunks(bill_id: int, query: str, top_k: int = 5,
                                   hyper_mode: bool = False, bill_title: str = "") -> List[dict]:
    """Relevant document excerpts for a question. Not included; returns none."""
    return []
