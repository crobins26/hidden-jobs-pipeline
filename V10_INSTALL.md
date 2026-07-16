# Career Intelligence Center v10 — Desktop and Mobile Sync

## Files to replace at repository root
- index.html
- app.js
- styles.css
- sw.js
- manifest.json

## New files to add at repository root
- supabase-config.js
- SUPABASE_SCHEMA.sql

## Supabase setup

1. Create a free Supabase project.
2. Open SQL Editor → New query.
3. Paste all contents of `SUPABASE_SCHEMA.sql`.
4. Click Run.
5. Open Project Settings → API.
6. Copy the Project URL.
7. Copy the publishable key (or legacy anon public key).
8. Edit `supabase-config.js` in GitHub.
9. Replace the two placeholder values.
10. Never use a service_role or secret key in the public repository.

## Authentication settings

1. In Supabase, open Authentication → URL Configuration.
2. Set Site URL:
   `https://crobins26.github.io/hidden-jobs-pipeline/`
3. Add the same URL under Redirect URLs.
4. Under Authentication → Providers → Email, keep Email enabled.
5. For the easiest first setup, either confirm the signup email or temporarily disable email confirmation while creating your own account, then turn it back on.

## Deploy and use

1. Commit the files to main.
2. Wait 2–3 minutes.
3. Open the normal Chrome website and hard refresh.
4. Confirm Engine v10.0.
5. Click Sign In → Create Account.
6. Sign in on desktop.
7. Click Sync Now once.
8. Open the app on your phone.
9. Sign in with the same email/password.
10. Your saved jobs, application tracking, interviews, notes, and goals will load.

## First sync behavior

The first device that signs in uploads its current local data if the cloud account is empty.
The second device downloads that shared data.

After setup, changes automatically upload after a short delay. Sync Now forces a pull and push.

## Safety

The publishable key is designed for browser applications. Row Level Security restricts each signed-in user to their own row. Never publish a Supabase secret/service-role key.
