# Auction collection groups and source ownership

SetadScope separates the listing category from the collection that owns the
records. The two owning collections are independent:

- `collection_group=executive_agencies`: auctions belonging to executive agencies.
- `collection_group=amval_tamliki`: auctions belonging to the Organization for Collection and Sale of State-Owned Properties.

Both groups expose the same five categories. Clearance is not a shared group.

## Confirmed source registry

| Collection group | Category | Adapter | Endpoint / ownership parameters |
| --- | --- | --- | --- |
| executive_agencies | movable | EAUC | `/eauc/mainEstate-Load.action` |
| executive_agencies | immovable | EAUC | `/eauc/mainImmovable-Load.action` |
| executive_agencies | rental | EAUC | `/eauc/mainRental-Load.action` |
| executive_agencies | minor | EAUC | `/eauc/mainMinor-Load.action` |
| executive_agencies | clearance | Central Board | `tagCode=341,343` |
| amval_tamliki | movable | EAUC | `/eauc/mainEstate-Load.action` |
| amval_tamliki | immovable | EAUC | `/eauc/mainImmovable-Load.action` |
| amval_tamliki | rental | EAUC | `/eauc/mainRental-Load.action` |
| amval_tamliki | minor | EAUC | `/eauc/mainMinor-Load.action` |
| amval_tamliki | clearance | Central Board | `tagCode=342&selectedOrganization=5315` |

### Executive-agency clearance

```text
GET https://gw.setadiran.ir/api/centralboard/cards/
    ?tagCode=341,343
    &boardCode=3
    &searchTypeCode=0
    &isLogin=false
    &userRole=0
    &queryText=
    &pageNumber=0
    &pageSize=5
    &sort=score,desc
```

### Amval Tamliki clearance

```text
GET https://gw.setadiran.ir/api/centralboard/cards/
    ?tagCode=342
    &selectedOrganization=5315
    &boardCode=3
    &searchTypeCode=0
    &isLogin=false
    &userRole=0
    &queryText=
    &pageNumber=0
    &pageSize=5
    &sort=score,desc
```

Both use the Central Board response adapter, which reads the top-level
`content` array and `totalPages` / `totalElements`. The source configurations,
filters, progress states, raw directories, ingestion histories and database
identities are independent.

The Amval Central Board source requires every returned row to contain
`orgId=5315`. A missing or different ID raises a source-context error before
the response is saved. This guard is separate from the existing EAUC guard,
which verifies `auctioneer.id=2` for the Amval EAUC session.

The EAUC routes are shared by path only: the executive session is bootstrapped
with `gateway=setad`, while the Amval session uses
`gateway=amvalTamliki`. Their session contexts and stored source identities
remain independent.

## CLI

Collect and import either clearance source independently:

```powershell
.\setad.ps1 collect-category -Category clearance -Group executive_agencies
.\setad.ps1 collect-category -Category clearance -Group amval_tamliki
```

Other categories continue to use the same explicit group selector:

```powershell
.\setad.ps1 collect-category -Category movable -Group executive_agencies
.\setad.ps1 collect-category -Category movable -Group amval_tamliki
.\setad.ps1 collect-category -Category immovable -Group amval_tamliki
```

The category-only legacy command remains compatible:
- `collect-category -Category movable` resolves to `executive_agencies`.
- `collect-category -Category clearance` resolves to executive-agency clearance.
- Pass `-Group amval_tamliki` to collect the Amval clearance source.

The Python collector supports one category or all categories in a group:

```powershell
python -m setad_scope.collectors.fetch_auction_categories --group executive_agencies --category clearance
python -m setad_scope.collectors.fetch_auction_categories --group amval_tamliki --category clearance
python -m setad_scope.collectors.fetch_auction_categories --group executive_agencies
python -m setad_scope.collectors.fetch_auction_categories --group amval_tamliki
```

Import the latest completed snapshot:

```powershell
python -m app.auction_category_jobs --group executive_agencies --category clearance
python -m app.auction_category_jobs --group amval_tamliki --category clearance
```

## Storage and migration

Auction rows carry both `collection_group` and `category`. Their identity is:

```text
(collection_group, source, source_party_id)
```

Central Board sources use distinct source names:
- `setad_clearance_executive_agencies`
- `setad_clearance_amval_tamliki`

Alembic revision `0012` separates rows that revision `0010` previously moved
into the old shared scope. Rows with raw `orgId=5315`, `tagCode=342`, or an
Amval organization name are reassigned to Amval; remaining rows are assigned
to executive agencies. The migration preserves each auction's JSONB payload,
first-seen timestamp and normalized data. Historical ingestion-run records
without a per-record source link are retained under the executive collection,
the legacy default.

Raw historical JSON snapshots are not deleted. New executive clearance
snapshots are stored under `data/raw/auctions/clearance`; Amval clearance
snapshots are stored under `data/raw/auctions/amval_tamliki/clearance`.

## API filters and collection status

- `GET /api/auctions?category=clearance&collection_group=executive_agencies`
- `GET /api/auctions?category=clearance&collection_group=amval_tamliki`
- `GET /api/auctions?category=clearance&collection_group=all`
- `GET /api/search?kind=auction&collection_group=amval_tamliki`
- `GET /api/auctions/export.xlsx?category=clearance&collection_group=amval_tamliki`
- `POST /api/collection/auctions/clearance/run?collection_group=amval_tamliki`
- `GET /api/collection/auctions/clearance/status?collection_group=amval_tamliki`
- `GET /api/collection/auctions/history?collection_group=amval_tamliki`

For listing and search APIs, `collection_group=all` includes both owning
collections. Selecting clearance for both groups in the dashboard runs two
distinct sources sequentially; neither is labeled or stored as shared.
