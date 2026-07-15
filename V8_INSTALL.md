# Career Intelligence Center v8 — Permanent Saved Jobs

## What this version fixes

The daily feed can refresh, add new jobs, and remove expired jobs without deleting your saved or tracked jobs.

When you click **Save** or **Track**:
- the complete job record is copied into a permanent browser archive;
- the job remains in the **Saved Jobs** tab even if it disappears from tomorrow's feed;
- its original company, title, salary, location, application link, fit score, and risk remain available;
- your application status, notes, resume used, and follow-up date remain attached.

A job leaves the archive only when you click **Delete permanently**.

## Replace in GitHub

Upload and replace:

- `index.html`
- `app.js`
- `styles.css`
- `sw.js`
- `manifest.json`

Also replace:

- `.github/workflows/daily_scan.yml`

The workflow included here contains the v7.4 delayed-schedule correction.

Do not delete:
- `data/jobs.json`
- `data/company_sources.csv`
- `data/search_config.json`
- `data/candidate_profile.json`
- `scripts/scan_jobs.py`
- `icons/`

## Install / refresh

1. Upload the replacement files while preserving folders.
2. Commit to `main`.
3. Wait 2–3 minutes for GitHub Pages.
4. Open the website in normal Chrome.
5. Refresh twice.
6. Confirm the header says **Engine v8.0**.
7. On Android, completely close the installed app.
8. Reopen it.
9. If it still shows v7.3, uninstall the home-screen app only, then reinstall it from Chrome. Your saved data normally remains unless Chrome site data is cleared.

## Backups

Browser storage is permanent on that device, but it is not a cloud database.
Use **Saved Jobs → Export Saved Jobs** weekly.
Do not clear Chrome site data for the GitHub Pages website unless you have exported a backup.
