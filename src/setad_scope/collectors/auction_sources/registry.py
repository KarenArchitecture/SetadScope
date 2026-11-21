from __future__ import annotations

from .amval_tamliki import SOURCES as AMVAL_TAMLIKI_SOURCES
from .executive_agencies import SOURCES as EXECUTIVE_AGENCIES_SOURCES

DEFAULT_COLLECTION_GROUP = "executive_agencies"
COLLECTION_GROUPS = ("executive_agencies", "amval_tamliki")
SOURCE_REGISTRY = {
    "executive_agencies": EXECUTIVE_AGENCIES_SOURCES,
    "amval_tamliki": AMVAL_TAMLIKI_SOURCES,
}
CATEGORIES_BY_GROUP = {
    group: tuple(sources.keys())
    for group, sources in SOURCE_REGISTRY.items()
}
ALL_CATEGORIES = tuple(dict.fromkeys(
    category
    for categories in CATEGORIES_BY_GROUP.values()
    for category in categories
))


def resolve_collection_group(category: str, collection_group: str | None = None) -> str:
    """Resolve legacy calls while keeping source ownership explicit.

    The existing central-board clearance source is organization 5315 and belongs
    to Amval Tamliki. Other legacy category-only calls continue to target the
    executive-agencies collection unless a group is supplied explicitly.
    """
    group = collection_group
    if group is None:
        group = "amval_tamliki" if category == "clearance" else DEFAULT_COLLECTION_GROUP
    if group not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown collection group: {group}")
    if category not in SOURCE_REGISTRY[group]:
        available = ", ".join(CATEGORIES_BY_GROUP[group])
        raise ValueError(
            f"Category {category!r} is not configured for {group!r}. Available: {available}"
        )
    return group


def categories_for_group(collection_group: str) -> tuple[str, ...]:
    if collection_group not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown collection group: {collection_group}")
    return CATEGORIES_BY_GROUP[collection_group]


def source_for(category: str, collection_group: str | None = None):
    group = resolve_collection_group(category, collection_group)
    return SOURCE_REGISTRY[group][category]
