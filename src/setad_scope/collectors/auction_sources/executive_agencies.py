from .source import build_eauc_sources

COLLECTION_GROUP = "executive_agencies"

# Four EAUC categories are currently confirmed for this group. A fifth category
# is deliberately not fabricated until its real endpoint is identified.
SOURCES = build_eauc_sources(COLLECTION_GROUP)
