"""长期记忆系统：写入、召回、衰减。"""

from .extractor import extract_memories, extract_memories_with_llm, extract_profile_updates
from .retriever import recall, build_memory_block, profile_snapshot
from .store import (
    CATEGORY_LABELS,
    add_memory,
    deactivate_memory,
    list_memories,
    mark_recalled,
    memory_stats,
    search_by_embedding,
)

__all__ = [
    "CATEGORY_LABELS",
    "add_memory",
    "build_memory_block",
    "deactivate_memory",
    "extract_memories",
    "extract_memories_with_llm",
    "extract_profile_updates",
    "list_memories",
    "mark_recalled",
    "memory_stats",
    "profile_snapshot",
    "recall",
    "search_by_embedding",
]
