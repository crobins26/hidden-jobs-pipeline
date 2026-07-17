# Career Intelligence Center v14 — Full Multi-Source Engine

## What is now automated

- Adzuna
- TheirStack when credits are available
- Greenhouse
- Lever
- Ashby
- SmartRecruiters
- Workday public CXS career sites configured in `data/career_sources.csv`
- Recruitee public careers feeds configured in `data/career_sources.csv`
- Personio public XML feeds configured in `data/career_sources.csv`
- Direct employer career pages exposing JobPosting JSON-LD
- Direct employer XML sitemaps containing JobPosting pages

## Employer-specific configurable platforms

The following do not expose one universal anonymous endpoint across every employer:

- BambooHR
- Teamtailor
- Jobvite
- iCIMS
- Oracle Recruiting
- SAP SuccessFactors

Version 14 scans them through the generic JSON-LD or sitemap connector after the
employer's public career URL is added to `data/career_sources.csv`.

## Discovery-only sources

These are intentionally not scraped:

- Built In
- Wellfound
- Welcome to the Jungle

They may still appear through Adzuna or TheirStack. The app labels them as
discovery-only instead of pretending it queried them directly.

## Daily-feed behavior

- $130,000 salary floor when salary is published
- Strong-fit unpublished-salary jobs can remain
- Maximum 100 jobs
- Maximum 3 roles per company
- New Today jobs rank before repeated inventory
- Dead and expired links are removed
- `data/seen_jobs.json` remembers previous discoveries
- Saved Jobs remain separate and are never deleted by the daily scan

## GitHub files to replace

- `.github/workflows/daily_scan.yml`
- `scripts/scan_jobs.py`
- `index.html`
- `app.js`
- `styles.css`
- `sw.js`
- `manifest.json`

## New GitHub files to add

- `data/career_sources.csv`
- `data/seen_jobs.json`
- `data/source_coverage.json`

Do not replace:

- `supabase-config.js`
- `SUPABASE_SCHEMA.sql`
- `data/candidate_profile.json`
- `data/search_config.json`
- your Supabase data or storage

## Configure employer-specific sources

Edit `data/career_sources.csv`.

Connector options:

- `workday`
  - endpoint is the employer's public Workday CXS jobs endpoint
- `recruitee`
  - endpoint is only the Recruitee company subdomain
- `personio`
  - endpoint is the public Personio XML URL
- `jsonld`
  - endpoint is a public employer career page
- `sitemap`
  - endpoint is a public XML sitemap

Start each new row with `enabled=no`, test the endpoint, then change it to `yes`.

## Test

1. Commit the files.
2. Run Daily Hidden Jobs Scan manually.
3. Expand Show scan summary.
4. Confirm Matches, New today, and Qualified after validation.
5. Open the app and refresh.
6. Confirm Engine v14.0.
7. Open Dashboard → Search Source Coverage.
8. Confirm exactly which sources were active.
