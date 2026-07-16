# Version 11 Supabase Startup Fix

This version fixes the cached-placeholder problem.

Replace at the repository root:
- index.html
- app.js
- styles.css
- sw.js
- manifest.json

Keep your existing:
- supabase-config.js
- SUPABASE_SCHEMA.sql
- data/
- scripts/
- .github/

After committing:
1. Wait 2–3 minutes.
2. Open the normal website in Chrome.
3. Press Ctrl+F5 twice.
4. Confirm the header says Engine v11.0.
5. Cloud Sync should say `Ready — sign in`.
6. The diagnostic line should say `Configuration confirmed.`

If the installed phone app still shows an older version:
1. Open the website in Chrome first.
2. Refresh twice.
3. Remove the home-screen shortcut.
4. Reinstall from Chrome.
5. Do not clear Chrome site data.
