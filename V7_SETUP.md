# Career Intelligence Center v7 — Broad Search Setup

## What changed

- Optional broad search across 350,000+ job sources through TheirStack
- Fallback scans of the existing Greenhouse, Lever, and Ashby company registry
- Strict title relevance and domain-gap penalties
- 96% maximum score; no automatic 99% matches
- Salary confidence and suspicious-range detection
- Interview probability
- Estimated application time
- Recommended resume version
- Cover-letter recommendation
- Freshness classification
- Top 10 Today designation
- Main risk/gap on each job card

## Required one-time step for broad coverage

The broad multi-ATS search requires a TheirStack API key.

1. Create a TheirStack account and obtain an API key.
2. In GitHub, open your `hidden-jobs-pipeline` repository.
3. Go to **Settings → Secrets and variables → Actions**.
4. Click **New repository secret**.
5. Name it exactly: `THEIRSTACK_API_KEY`
6. Paste the API key as the secret value.
7. Save.
8. Run **Daily Hidden Jobs Scan** manually once.

Without the secret, the app still runs the existing direct ATS board scanner. With the secret, it adds broad coverage across Workday, iCIMS, SmartRecruiters, Oracle, SuccessFactors, Jobvite, Teamtailor, Recruitee, BambooHR, Greenhouse, Lever, Ashby, and direct career pages available through the provider.

## Replace in GitHub

Replace:
- `.github/workflows/daily_scan.yml`
- `scripts/scan_jobs.py`
- `data/search_config.json`
- `data/candidate_profile.json`
- `index.html`
- `app.js`
- `styles.css`
- `sw.js`
- `README.md`

Keep:
- `data/company_sources.csv`
- `data/jobs.json`
- `icons/`
