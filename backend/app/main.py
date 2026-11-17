from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from app.services.auction_reader import load_auctions


app = FastAPI(
    title="SetadScope API",
    description="API for browsing collected public Setad auction listings.",
    version="0.1.0",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/auctions")
def get_auctions(
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    auctions = load_auctions()

    if search:
        term = search.casefold()
        auctions = [
            item for item in auctions
            if term in (item.get("title") or "").casefold()
            or term in (item.get("organization") or "").casefold()
            or term in (item.get("city") or "").casefold()
        ]

    total = len(auctions)
    start = (page - 1) * page_size
    return {
        "items": auctions[start : start + page_size],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
    }


@app.get("/api/auctions/{auction_party_id}")
def get_auction(auction_party_id: int) -> dict:
    for auction in load_auctions():
        if auction.get("id") == auction_party_id:
            return auction
    raise HTTPException(status_code=404, detail="Auction listing not found")
