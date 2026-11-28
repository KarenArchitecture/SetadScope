from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuctionSource:
    collection_group: str
    category: str
    source: str
    adapter: str
    base_url: str
    path: str
    default_rows: int = 30
    landing_url: str | None = None
    referer: str | None = None
    expected_auctioneer_id: str | None = None
    expected_organization_id: str | None = None
    fixed_params: tuple[tuple[str, str], ...] = ()


def build_eauc_sources(collection_group: str) -> dict[str, AuctionSource]:
    base_url = "https://eauc.setadiran.ir"
    # EAUC uses the same listing endpoints for different owning collections,
    # but the gateway selected during session bootstrap determines the dataset.
    gateway = "amvalTamliki" if collection_group == "amval_tamliki" else "setad"
    landing_url = f"{base_url}/eauc/welcome.action?gateway={gateway}"
    expected_auctioneer_id = "2" if collection_group == "amval_tamliki" else None
    routes = {
        "movable": ("/eauc/mainEstate-Load.action", "setad_main_estate", ()),
        "immovable": (
            "/eauc/mainImmovable-Load.action",
            "setad_immovable",
            (("propertySearchCriteriaDto.auctionType", "NON_PROPERTY"),),
        ),
        "rental": ("/eauc/mainRental-Load.action", "setad_rental", ()),
        "minor": ("/eauc/mainMinor-Load.action", "setad_minor", ()),
    }
    return {
        category: AuctionSource(
            collection_group=collection_group,
            category=category,
            source=source,
            adapter="eauc",
            base_url=base_url,
            path=path,
            default_rows=30,
            landing_url=landing_url,
            expected_auctioneer_id=expected_auctioneer_id,
            fixed_params=params,
        )
        for category, (path, source, params) in routes.items()
    }



def build_centralboard_clearance_source(collection_group: str) -> AuctionSource:
    """Build the owner-specific Central Board clearance source."""
    common_params = (
        ("boardCode", "3"),
        ("searchTypeCode", "0"),
        ("isLogin", "false"),
        ("userRole", "0"),
        ("queryText", ""),
        ("sort", "score,desc"),
    )
    if collection_group == "executive_agencies":
        source = "setad_clearance_executive_agencies"
        # Match the executive-agency view in the Central Board UI: exclude Amval Tamliki (org 5315).
        fixed_params = (("tagCode", "341,343"), ("notOrgId", "5315"), *common_params)
        expected_organization_id = None
    elif collection_group == "amval_tamliki":
        source = "setad_clearance_amval_tamliki"
        fixed_params = (("tagCode", "342"), ("selectedOrganization", "5315"), *common_params)
        expected_organization_id = "5315"
    else:
        raise ValueError(f"Unsupported Central Board collection group: {collection_group}")

    return AuctionSource(
        collection_group=collection_group,
        category="clearance",
        source=source,
        adapter="centralboard",
        base_url="https://gw.setadiran.ir",
        path="/api/centralboard/cards/",
        default_rows=5,
        referer="https://fe.setadiran.ir/centralboard/",
        expected_organization_id=expected_organization_id,
        fixed_params=fixed_params,
    )
