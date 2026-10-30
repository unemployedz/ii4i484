# Deployment

## Free-tier architecture

The repository contains the upstream Free Claude Code Python/FastAPI server, its Admin UI, provider integrations, and browser-based coding-session functionality. Intended architecture:

- **Render Free:** Python agent backend. It sleeps when idle; local files and settings are ephemeral.
- **Vercel Hobby:** optional separate frontend/landing page if a separate frontend is added. Vercel Functions are not a replacement for the long-running agent runtime.
- **Supabase Free:** authentication, after server-side authorization is implemented and tested.
- **Neon Free:** Postgres for durable app metadata/session records. Never store provider secrets in client-readable tables.

No paid Render plan, persistent disk, or paid model fallback is configured here.

## Security requirement before public deployment

This application can launch coding agents and execute tools against a workspace. It must not be exposed as an unrestricted public service.

Before public deployment, implement and test:
1. Authentication on every browser-facing route that can read or modify workspaces, sessions, provider settings, or secrets.
2. Server-side authorization so each user can access only their own workspace and sessions.
3. CSRF/origin protections for state-changing browser requests.
4. Server-side secret storage; never return provider API keys to browser code or logs.
5. Safe workspace isolation and command execution boundaries.
6. Rate limits and quotas so one user cannot exhaust free provider limits for everyone.

Do not assume the upstream Admin UI proxy-authentication option protects every Admin or browser-session route. Verify route coverage first.

## Render

The Render Blueprint selects the free web-service plan and intentionally has no persistent disk. Render Free services can sleep when idle, and local settings, provider credentials, and workspace files can be lost on restart or redeploy. Keep durable metadata in the database and expect users to reconnect/reselect ephemeral workspaces after a restart.

Create a Blueprint from this repository only after the security requirements above are satisfied. Confirm the service remains on the Free plan in the Render dashboard before deploying.

## Vercel

The current backend is a long-running Python/FastAPI service with coding-session processes and filesystem access. Vercel Hobby can host a separate frontend, but not the complete agent runtime as a conventional serverless function. Do not create a Vercel project until a separate frontend exists and is wired to the authenticated backend.

## Databases

Use separate, project-specific Supabase and Neon projects. Never reuse or modify unrelated existing databases. Keep Supabase service-role credentials and Neon connection strings server-side only. Enable row-level security on every user-facing table and validate ownership in backend code.

## Licensing

The imported upstream application is licensed under AGPL-3.0-only. Retain its license, notices, and required source-disclosure obligations when modifying or redistributing it. This project is independent and is not affiliated with Anthropic.
