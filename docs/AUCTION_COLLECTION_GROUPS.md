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
| shared | clearance | Central Board | `/api/centralboard/cards/` |

The four EAUC endpoints use the same response adapter and pagination contract in both owning collections, but they do **not** share the same initial session context. The executive-agency collector bootstraps its session with `gateway=setad`; the Amval collector must bootstrap with `gateway=amvalTamliki`. EAUC then serves different datasets through the same `mainEstate`, `mainImmovable`, `mainRental`, and `mainMinor` request paths.

For the Amval context, every non-empty EAUC page is checked against the known owning organization identity `auctioneer.id=2`. A page that contains another organization's ID, or contains no verifiable auctioneer identity, is rejected before it can be written to a completed raw snapshot or imported into PostgreSQL. This prevents a session-context regression from silently copying executive-agency records into the Amval collection. The two groups still share the same response adapter and pagination contract, while their session bootstrap, raw snapshots, ingestion runs, and database identities remain independent.

The Central Board clearance feed is different: the two observed UI contexts use the same request URL and parameters:
`tagCode=341,343`, `boardCode=3`, `searchTypeCode=0`, `isLogin=false`, `userRole=0`, `queryText=`, and `sort=score,desc`. It is therefore registered once as `collection_group=shared`, with one collector, one progress state, one ingestion history, and one stored copy of each card. The request does not use `selectedOrganization=5315`.

The previous 5315-scoped Central Board records are preserved and migrated from `setad_clearance_5315/amval_tamliki` to `setad_clearance_shared/shared` by Alembic revision `0010`. Raw historical snapshots remain untouched; new shared snapshots are written under `data/raw/auctions/shared/clearance`.

Only four EAUC categories are currently confirmed for each owning collection. The shared Central Board clearance feed is shown as a third source choice in the UI, not duplicated under either owning collection.

The live EAUC endpoints were observed returning empty arrays during endpoint discovery. Their current data volume and live pagination still require a later verification run; the registry and parser are based on the supplied request shapes and existing EAUC fixtures.

## CLI

Collect one category from either owning collection:

```powershell
.\setad.ps1 collect-category -Category movable -Group executive_agencies
.\setad.ps1 collect-category -Category movable -Group amval_tamliki
.\setad.ps1 collect-category -Category immovable -Group amval_tamliki
```

Collect the shared Central Board feed once:

```powershell
.\setad.ps1 collect-category -Category clearance -Group shared
```

The category-only legacy command remains compatible:
- `collect-category -Category movable` resolves to `executive_agencies`.
- `collect-category -Category clearance` resolves to `shared`.

The Python collector also supports one category or every category registered for a group:

```powershell
python -m setad_scope.collectors.fetch_auction_categories --group executive_agencies --category movable
python -m setad_scope.collectors.fetch_auction_categories --group amval_tamliki --category movable
python -m setad_scope.collectors.fetch_auction_categories --group shared --category clearance
python -m setad_scope.collectors.fetch_auction_categories --group executive_agencies
python -m setad_scope.collectors.fetch_auction_categories --group amval_tamliki
```

Import only the latest completed snapshot:

```powershell
python -m app.auction_category_jobs --group amval_tamliki --category movable
python -m app.auction_category_jobs --group shared --category clearance
```

## Storage and idempotency

Auction rows carry both `collection_group` and `category`. Their identity is:

```text
(collection_group, source, source_party_id)
```

This permits the same EAUC endpoint and source ID to appear independently in the two owning collections without one upsert overwriting the other. The shared Central Board feed has exactly one identity scope, so collecting it from either UI context cannot create a second copy.

Migration `0009` conservatively backfills the original source identities. Migration `0010` moves historical 5315-scoped clearance records to the shared source without deleting their JSONB payloads or first-seen timestamps. Tender records remain ungrouped.

## API filters

- `GET /api/auctions?category=movable&collection_group=executive_agencies`
- `GET /api/auctions?category=movable&collection_group=amval_tamliki`
- `GET /api/auctions?category=clearance&collection_group=shared`
- `GET /api/search?kind=auction&collection_group=amval_tamliki`
- `GET /api/auctions/export.xlsx?category=movable&collection_group=amval_tamliki`
- `POST /api/collection/auctions/movable/run?collection_group=amval_tamliki`
- `GET /api/collection/auctions/movable/status?collection_group=amval_tamliki`
- `GET /api/collection/auctions/history?collection_group=shared`

For listing and search APIs, `collection_group=all` includes all three scopes. Exported rows include the collection group as an explicit column. Each scope has its own progress and collection history.
