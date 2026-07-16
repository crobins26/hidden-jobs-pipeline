# Career Intelligence Center v13 — Resilient Multi-Source Search

## Search architecture

Primary broad discovery:
- Adzuna API

Optional supplemental discovery:
- TheirStack, only when credits are available

Direct employer / ATS verification:
- Greenhouse
- Lever
- Ashby
- SmartRecruiters company boards configured in `data/company_sources.csv`

The engine combines all providers, removes duplicates, prefers official ATS links,
scores every role, and publishes no more than 100 jobs each day.

## Adzuna setup

1. Register for an Adzuna developer account.
2. Copy the Application ID.
3. Copy the Application Key.
4. In GitHub, open:
   Settings → Secrets and variables → Actions
5. Add repository secret:
   - Name: `ADZUNA_APP_ID`
   - Value: your Adzuna Application ID
6. Add repository secret:
   - Name: `ADZUNA_APP_KEY`
   - Value: your Adzuna Application Key

TheirStack remains optional. Leave its secret in place; the scanner uses it only
when credits are available.

## Replace in GitHub

Replace:
- `.github/workflows/daily_scan.yml`
- `scripts/scan_jobs.py`
- `index.html`
- `app.js`
- `styles.css`
- `sw.js`
- `manifest.json`

Keep:
- `supabase-config.js`
- `SUPABASE_SCHEMA.sql`
- `data/candidate_profile.json`
- `data/search_config.json`
- `data/company_sources.csv`
- all saved Supabase data

## Test

1. Commit the files.
2. Run Daily Hidden Jobs Scan manually.
3. Expand Show scan summary.
4. Confirm Provider status reports Adzuna and Direct ATS.
5. Open the app and refresh.
6. Confirm the header says Engine v13.0.

## Direct-link honesty

Adzuna is a discovery source and may return a redirect URL. When the same role is
also found through Greenhouse, Lever, Ashby, or SmartRecruiters, the direct ATS
link automatically wins. Roles found only through Adzuna remain clearly labeled
as broad-discovery results.
