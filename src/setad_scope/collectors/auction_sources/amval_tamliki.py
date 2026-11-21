from .source import build_eauc_sources

COLLECTION_GROUP = "amval_tamliki"

# The four EAUC categories are the same listing families, collected independently
# for this owning collection. Central-board clearance is a separate shared source.
SOURCES = build_eauc_sources(COLLECTION_GROUP)
