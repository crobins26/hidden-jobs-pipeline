# Hidden Jobs Pipeline

A phone-friendly progressive web app that scans direct employer career boards, filters senior leadership roles, and ranks them for Cernice Robinson.

## What is already configured

- 146 starter company career boards across Greenhouse, Lever, and Ashby.
- Capacity for 1,000+ company-board rows in `data/company_sources.csv`.
- Daily GitHub Actions refresh.
- Direct employer application links.
- Filters for remote/Midwest, $150K+, career track, freshness, and fit.
- Installable Android PWA.

## Important truth

The app can technically scan 1,000+ configured boards, but this starter package contains 146 board records. ATS slugs change, and some companies use Workday or custom career sites, so each source must be validated. The separate ChatGPT morning automation is broader and is not limited to this CSV.

## Publish free with GitHub Pages

1. Create a new public GitHub repository named `hidden-jobs-pipeline`.
2. Upload every file and folder from this package.
3. Open **Settings → Pages**.
4. Under **Build and deployment**, choose **Deploy from a branch**.
5. Select `main` and `/ (root)`, then save.
6. Open the Pages URL GitHub gives you.
7. On Android Chrome, tap the three dots → **Add to Home screen** → **Install**.

## Turn on the daily refresh

1. Open the repository's **Actions** tab.
2. Enable workflows if GitHub asks.
3. Open **Daily Hidden Jobs Scan**.
4. Select **Run workflow** once to test.
5. The scheduled workflow runs daily and commits a refreshed `data/jobs.json`.

GitHub schedules use UTC and can occasionally start later than the exact minute. The included time is set at 6:30 a.m. Central, with daylight-saving-time handling.

## Add companies

Add rows to `data/company_sources.csv`:

`Company Name,greenhouse,board-slug,yes`

Supported ATS values:
- `greenhouse`
- `lever`
- `ashby`

The slug is the final company-specific portion of the public ATS job-board URL.

## Practical next upgrade

For true 1,000+ coverage including Workday and custom career sites, connect a licensed job-data/search API or add a server-side discovery service. Blindly scraping 1,000 arbitrary sites from GitHub Actions is brittle and can violate site rules; the included scanner uses public ATS job-board endpoints.


## Direct application links

Each job title and the **Open job & apply** button link directly to the employer or its official ATS posting in a new browser tab.


## Application tracking

- Each job card includes a **Mark Applied** button.
- Applied status is saved on the device using browser local storage.
- The dashboard shows **Applied this week**, calculated Monday through Sunday.
- Tapping **Applied ✓** again removes the applied status.
- Tracking remains on the same device and browser unless site data is cleared.


# Version 4 — Career Intelligence Center

Added:
- Weekly and daily application goals
- Persistent application statuses
- Application pipeline table
- Follow-up dates
- Resume-version tracking
- Cover-letter tracking
- Recruiter/contact notes
- Interview tracker
- Resume conversion analytics
- Application-funnel analytics
- CSV export

## Storage model

Tracking data is stored in browser local storage. It remains on the same browser/device unless browser site data is cleared. Use the CSV export regularly as a backup. Cross-device sync requires a database/backend and is not included in this static GitHub Pages version.


# Version 5 — Obtainable Role Search Strategy

- $130,000 threshold
- Senior Customer Success Manager through Director prioritized
- Selective Senior Director, Head, and VP stretch roles
- Priority Apply / Strong Opportunity / Stretch ranking
- Strong-fit roles with unpublished salary remain visible


# Version 6 — Resume Studio

Added a private, browser-based Resume Studio:
- Uploads a DOCX résumé locally in the browser
- Compares it with a pasted job description
- Calculates a keyword match score
- Recommends the strongest resume lane
- Identifies matched and missing keywords
- Reorders evidence and achievement bullets
- Generates an editable tailored resume draft
- Downloads a Word-compatible `.doc` file
- Creates a detailed AI rewrite prompt for ChatGPT

## Privacy

Do not upload your master résumé into the public GitHub repository. Use the Resume Studio upload control inside the live app. The résumé text is read in the browser and is not written into the repository.

## Important limitation

The built-in generator is rules-based. A true AI rewrite requires a private server-side API integration. Never place an OpenAI or other AI API key inside a public GitHub Pages application.


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
