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
