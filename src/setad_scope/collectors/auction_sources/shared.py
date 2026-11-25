from .source import AuctionSource

COLLECTION_GROUP = "shared"

# Both observed UI contexts issue the same central-board request and return
# the same card feed. Keep one source identity and one collector to avoid
# duplicating the same cards in PostgreSQL.
SOURCES = {
    "clearance": AuctionSource(
        collection_group=COLLECTION_GROUP,
        category="clearance",
        source="setad_clearance_shared",
        adapter="centralboard",
        base_url="https://gw.setadiran.ir",
        path="/api/centralboard/cards/",
        default_rows=50,
        referer="https://fe.setadiran.ir/centralboard/",
        fixed_params=(
            ("tagCode", "341,343"),
            ("boardCode", "3"),
            ("searchTypeCode", "0"),
            ("isLogin", "false"),
            ("userRole", "0"),
            ("queryText", ""),
            ("sort", "score,desc"),
        ),
    ),
}
