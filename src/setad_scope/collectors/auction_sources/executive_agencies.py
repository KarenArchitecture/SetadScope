from .source import build_centralboard_clearance_source, build_eauc_sources

COLLECTION_GROUP = "executive_agencies"

# The four EAUC listing families and this group's Central Board clearance feed
# are separate source configurations under the same owning collection.
SOURCES = build_eauc_sources(COLLECTION_GROUP)
SOURCES["clearance"] = build_centralboard_clearance_source(COLLECTION_GROUP)
