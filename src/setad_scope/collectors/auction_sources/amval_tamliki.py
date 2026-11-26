from .source import build_centralboard_clearance_source, build_eauc_sources

COLLECTION_GROUP = "amval_tamliki"

# Four EAUC listing families plus the independently scoped Amval Central Board
# clearance feed. The latter is deliberately not shared with executive agencies.
SOURCES = build_eauc_sources(COLLECTION_GROUP)
SOURCES["clearance"] = build_centralboard_clearance_source(COLLECTION_GROUP)
