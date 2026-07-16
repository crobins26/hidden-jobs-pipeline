# Version 11.1 — Supabase Library Loader Fix

The Version 11 index file accidentally omitted:
- the Supabase browser library; and
- `supabase-config.js`.

That caused the message: `Supabase library unavailable`.

Replace at the repository root:
- `index.html`
- `sw.js`

Do not replace your configured `supabase-config.js`.

After committing:
1. Wait 2–3 minutes.
2. Open the normal website in Chrome.
3. Press Ctrl+F5 twice.
4. Confirm the header says Engine v11.1.
5. Cloud Sync should say `Ready — sign in`.
6. The diagnostic line should say `Configuration confirmed.`

This version tries jsDelivr first and unpkg second. If one CDN is blocked or temporarily unavailable, the other is used automatically.
