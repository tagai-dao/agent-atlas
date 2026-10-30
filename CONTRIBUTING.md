# Contributing

Use a feature branch or isolated worktree. Install locked dependencies with
`npm ci --ignore-scripts --no-audit --no-fund`, then run the Python regression suite
and `npm run check`. For deployment changes also run `npm run self-host:build` and
a self-host dry run against an independent local config.

Keep the existing production config and automation defaults intact. Do not commit
credentials, `.sync-state`, raw research or personal deployment files. Data PRs
must document sources, coverage, snapshot blocks/hashes, identity changes and
validation. Preserve manual evidence review and contract-address asset identity.

Do not label public X statements as wallet-control proof. Do not infer trades from
ordinary transfers or holdings from historical buys, sells or mint counts.
Retain third-party notices. Please explain behavior changes and validation in PRs.
