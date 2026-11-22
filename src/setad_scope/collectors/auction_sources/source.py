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
