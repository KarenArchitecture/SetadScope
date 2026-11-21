from .source import AuctionSource, build_eauc_sources

COLLECTION_GROUP = "amval_tamliki"

SOURCES = {
    **build_eauc_sources(COLLECTION_GROUP),
    "clearance": AuctionSource(
        collection_group=COLLECTION_GROUP,
        category="clearance",
        source="setad_clearance_5315",
        adapter="centralboard",
        base_url="https://gw.setadiran.ir",
        path="/api/centralboard/cards/",
        default_rows=5,
        referer="https://fe.setadiran.ir/centralboard/",
        fixed_params=(
            ("tagCode", "342"),
            ("selectedOrganization", "5315"),
            ("boardCode", "3"),
            ("searchTypeCode", "0"),
            ("isLogin", "false"),
            ("userRole", "0"),
            ("queryText", ""),
            ("sort", "score,desc"),
        ),
    ),
}
