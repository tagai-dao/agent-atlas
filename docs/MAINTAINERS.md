# Maintainer production compatibility

- `wrangler.jsonc` remains the sole configuration source for the maintained deployment. Its account, custom domain, D1 binding, existing variables/secrets and disabled workers.dev/preview URLs are unchanged.
- Existing npm dev/build/deploy commands, main-branch Workers Builds and collection/normalization scripts retain their existing defaults.
- The optional `ATLAS_WRANGLER_CONFIG` path is set only by the new self-host commands. Without it Vite uses the existing Sites/connector preview plugins and root production config exactly as before.
- Self-host commands use a separate ignored root config, disable local mock identity/connector preview integration, retain all public read-only routes and never enable evidence writes.
- Do not set `ATLAS_WRANGLER_CONFIG` on the maintained production runner. It is not needed by the existing automation.
- Public dataset snapshots, UI/branding, evidence classifications and manual review states are not modified by this change.
- Use an isolated checkout for releases and development. `.sync-state` and collector locks belong to the primary maintenance checkout; do not stage another task's work.
- A feature-branch PR must be reviewed and merged deliberately. Publishing a branch does not authorize deploying it over production. After a later approved merge, the existing main-branch pipeline remains the deployment path.
