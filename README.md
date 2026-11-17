# SetadScope

SetadScope is a data collection and analytics project for monitoring public tenders and auctions published on the Setad Iran platform.

## Initial goals

- Collect tender and auction records from the public-facing platform.
- Normalize and store records in a database.
- Track changes and support daily or weekly reporting.
- Produce searchable tables, exports, and analytical charts.
- Add AI-assisted interpretation only after the underlying data pipeline is reliable.

## Development principles

- Start with a small, testable data pipeline.
- Keep website access, parsing, storage, and analytics separated.
- Never commit credentials, session cookies, API keys, or local environment files.
- Respect the platform's access rules and rate limits.

## Project status

Early setup — architecture and data-source behavior are being validated.
