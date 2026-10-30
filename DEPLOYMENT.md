# Deployment

## Render (recommended for the complete app)

This repository keeps the original Free Claude Code FastAPI server and its browser Admin UI together. Deploy it as a Docker web service on Render using `render.yaml`.

1. In Render, create a Blueprint and select this repository.
2. Review the service and deploy it. The current blueprint uses Render's free web-service plan and therefore has ephemeral storage: settings, provider credentials, and local workspaces may be lost when the instance restarts or redeploys.
3. For persistent sessions and project files, switch to a paid Render instance and attach a persistent disk mounted at `/data`. Review Render pricing before enabling a paid plan.
4. Configure provider credentials in the app's Admin UI only after access is restricted.

## Security warning

Free Claude Code is designed primarily for a trusted local machine. A public deployment exposes a powerful coding environment capable of running tools and changing files. Do not put this service on the public internet until you have verified the upstream authentication and remote Admin access behavior for your exact version, restricted access at the network/identity layer, and stored provider credentials only in server-side secrets. Do not share the public URL as an unrestricted service.

## Vercel

The original application is a long-running Python/FastAPI service with coding-session processes and filesystem access. Vercel Functions are not a suitable host for that backend. Use Render for the complete application. Vercel can host a separate static landing page or client later, but it cannot replace the persistent Render runtime.

## Source

The application source is imported from the upstream Free Claude Code project by the GitHub Actions workflow `Import Free Claude Code source`. Run it from the Actions tab after this workflow is available. The upstream project is licensed under AGPL-3.0; retain its license and notices when modifying or redistributing it.
