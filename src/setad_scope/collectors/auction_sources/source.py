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
    fixed_params: tuple[tuple[str, str], ...] = ()


def build_eauc_sources(collection_group: str) -> dict[str, AuctionSource]:
    base_url = "https://eauc.setadiran.ir"
    landing_url = base_url + "/eauc/welcome.action?gateway=setad"
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
            fixed_params=params,
        )
        for category, (path, source, params) in routes.items()
    }
