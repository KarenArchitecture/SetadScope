# Multi-source auction collection

SetadScope separates an auction's owning collection from its auction category.

- `collection_group=executive_agencies`: the executive-agency collection.
- `collection_group=amval_tamliki`: the Organization for Collection and Sale of State-Owned Properties collection.
- `category`: the shared listing type, such as `movable`, `immovable`, `rental`, `minor`, or `clearance`.

## Confirmed source registry

| Collection group | Category | Adapter | Endpoint |
| --- | --- | --- | --- |
| executive_agencies | movable | EAUC | `/eauc/mainEstate-Load.action` |
| executive_agencies | immovable | EAUC | `/eauc/mainImmovable-Load.action` |
| executive_agencies | rental | EAUC | `/eauc/mainRental-Load.action` |
| executive_agencies | minor | EAUC | `/eauc/mainMinor-Load.action` |
| amval_tamliki | movable | EAUC | `/eauc/mainEstate-Load.action` |
| amval_tamliki | immovable | EAUC | `/eauc/mainImmovable-Load.action` |
| amval_tamliki | rental | EAUC | `/eauc/mainRental-Load.action` |
| amval_tamliki | minor | EAUC | `/eauc/mainMinor-Load.action` |
| amval_tamliki | clearance | Central Board | `/api/centralboard/cards/` |

The four EAUC endpoints use the same response adapter and pagination contract in both groups. Each group still gets separate raw snapshots, ingestion runs, and database identities. The Central Board endpoint remains scoped to `selectedOrganization=5315` and is registered only for Amval Tamliki.

Only four categories are currently registered for `executive_agencies`: the supplied endpoint information does not identify a fifth executive-agency category. Add it to that group's registry only after its actual endpoint is known; do not reuse the Amval Tamliki clearance endpoint by assumption.

The live EAUC endpoints were observed returning empty arrays during endpoint discovery. Their current data volume and live pagination still require a later verification run; the registry and parser are based on the supplied request shapes and the existing EAUC fixtures.

## CLI

Collect one category:

```powershell
python -m setad_scope.collectors.fetch_auction_categories --group executive_agencies --category movable
python -m setad_scope.collectors.fetch_auction_categories --group amval_tamliki --category movable
```

Collect every configured category in one group:

```powershell
python -m setad_scope.collectors.fetch_auction_categories --group executive_agencies
python -m setad_scope.collectors.fetch_auction_categories --group amval_tamliki
```

Import the latest completed snapshot:

```powershell
python -m app.auction_category_jobs --group amval_tamliki --category movable
python -m app.auction_category_jobs --group amval_tamliki
```

The category-only legacy CLI remains compatible. A legacy `clearance` invocation resolves to `amval_tamliki`; the other category-only invocations resolve to `executive_agencies`.

## Storage and idempotency

Auction rows carry both `collection_group` and `category`. Their identity is:

```text
(collection_group, source, source_party_id)
```

This allows the same endpoint/source and listing ID to exist in both groups without one upsert overwriting the other. Existing source identities are conservatively backfilled by Alembic revision `0009`:

- `setad_clearance_5315` → `amval_tamliki`
- the four existing EAUC sources → `executive_agencies`

The migration aborts if an existing auction has an unrecognized source, rather than silently assigning it to the wrong group. Historical auction ingestion runs are backfilled from their category; tender runs remain ungrouped.

Raw snapshots for the original executive-agency collector keep their existing `data/raw/auctions/{category}` paths. Amval Tamliki snapshots are isolated under `data/raw/auctions/amval_tamliki/{category}`. The importer has a read-only compatibility fallback for the previous Central Board clearance manifest.

## API filters

- `GET /api/auctions?category=movable&collection_group=amval_tamliki`
- `GET /api/search?kind=auction&collection_group=amval_tamliki`
- `GET /api/auctions/export.xlsx?category=movable&collection_group=amval_tamliki`
- `POST /api/collection/auctions/movable/run?collection_group=amval_tamliki`
- `GET /api/collection/auctions/movable/status?collection_group=amval_tamliki`
- `GET /api/collection/auctions/history?collection_group=amval_tamliki`

For listing and search APIs, `collection_group=all` is the default and includes both groups. Exported rows include the collection group as an explicit column. Existing category-only collection status/run routes remain available and resolve to their historical group.
