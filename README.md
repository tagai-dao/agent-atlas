# Agent ID ATLAS

Open-source, self-hostable BNB Chain `.ai` Agent ID directory and activity explorer.
可独立部署的只读 Agent ID 目录、交易与 NFT 活动、持仓及每日注册走势图。

**[Maintained public instance](https://agent-id.tagai.fun/)** ·
**[Self-host deployment guide / 自托管教程](docs/SELF_HOSTING.md)** ·
**[Data updates](docs/DATA_UPDATES.md)** · **[MIT license](LICENSE)**

## Features

- Search and filter Agent IDs, wallet addresses and public X associations; inspect source evidence and review states.
- Distinguish strong single-identity evidence, weak clues, excluded multi-ID images and pending evidence under `single-identity-v3`.
- Explore supported BSC token trades by contract address, with internal curves and external V2/V3 markets separated. Dynamic Flap discovery and same-symbol isolation are preserved.
- Inspect Relic mint events, unique mint transactions and quantities separately from current NFT holdings.
- Browse scoped holdings for all registered wallets: BNB, tracked actual ERC20 tokens and current Relic balances, with holder pagination and CSV exports.
- View daily first registrations in Beijing time (UTC+8), with 7-day / 30-day / all-time ranges, cumulative totals and CSV downloads.
- Use paginated directory, activity, holdings and resolve APIs. Live name verification uses an optional server-side BSC RPC.

A clone includes the **published snapshots**. Running the website requires neither a wallet nor the maintainer's computer, account, raw caches or scheduled tasks. Snapshot dates and coverage are shown in the UI and manifests; a deployment is not a live chain indexer.

## Quick start

Requires Node.js **22.13+**, npm and Git. Python **3.11+** is needed for the full regression suite or collecting fresh data.

```sh
git clone https://github.com/tagai-dao/agent-atlas.git
cd agent-atlas
npm ci --ignore-scripts --no-audit --no-fund
npm run self-host:init
npm run self-host:dev
```

Open `http://localhost:5173`. This uses the portable self-host configuration and no local Sites identity or connector service. Public evidence submission remains disabled server-side.

For a production build, edit the newly created **ignored** `wrangler.self-host.json` with your own Worker name and Cloudflare account ID, then follow [the deployment guide](docs/SELF_HOSTING.md). No D1 database is needed for the current read-only features.

## Validate

```sh
python3 -m venv .venv
# macOS/Linux; Windows: .venv\Scripts\activate
. .venv/bin/activate
python -m pip install -r scripts/activity/requirements.txt
python -m unittest discover -s tests -p 'test_*.py'
npm run check
npm run self-host:build
npm run self-host:dry-run
```

The self-host dry run builds and packages locally; `self-host:deploy` is the separate command that publishes to your Cloudflare account. [Wrangler's configuration reference](https://developers.cloudflare.com/workers/wrangler/configuration/) documents domains and bindings.

## Data, evidence and limitations

Current counts and timestamps are in `data/research.json`, `public/activity/manifest.json`, `public/holdings/manifest.json` and `public/holdings/registrations.json`; README totals are intentionally not frozen.

Public X association evidence is **not proof of wallet control**. Manual verification, extraction confidence and association strength are independent. Images containing multiple `.ai` identities do not establish image ownership associations. Incomplete source material stays pending.

Chain events retain transaction hashes and log indices. Historical events use the current identity snapshot and do not establish that a name was registered at the event time. Unsupported pools and other coverage boundaries are disclosed. Holdings cover the listed assets only; curve shares, unclaimed Flap shares, DeFi positions and arbitrary wallet assets are outside that scope. Daily registration counts deduplicate each token ID's first mint and exclude transfers, burns and re-mints; the last day is incomplete.

See [data collection and update instructions](docs/DATA_UPDATES.md) for prerequisites, fixed-block Multicall3 and failure handling. X collection needs your own authorized source; credentials are not bundled.

## Maintainer production compatibility

The root `wrangler.jsonc` and the existing `dev`, `build`, `deploy:cloudflare` commands continue to serve the maintained deployment. Self-hosting uses **separate commands and configuration**; do not copy production account, domain or database IDs. Existing main-branch Workers Builds and desktop synchronization are separate from a fork's setup. See [maintainer notes](docs/MAINTAINERS.md).

## License and contributions

Original application code and documentation use the **MIT License**. Third-party content, packages and trademarks retain their own terms; see [NOTICE.md](NOTICE.md). Keep public source attribution and coverage explanations when sharing datasets. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
