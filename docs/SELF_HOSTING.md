# 独立自托管部署 / Self-hosting

本教程使用 Cloudflare Workers 部署完整的只读应用，包括目录、X 证据、交易、NFT、持仓、注册走势图及 API/CSV。它不是仅上传 HTML 的静态站点。其他平台的 Node/Docker 生产运行方式尚未验证，本教程不宣称支持。

## 1. 获取与安装

需要 Git、Node.js 22.13 或更新版本、npm。Fork 仓库后 clone 自己的 fork；也可以直接 clone：

```sh
git clone https://github.com/tagai-dao/agent-atlas.git
cd agent-atlas
npm ci --ignore-scripts --no-audit --no-fund
npm run self-host:init
npm run self-host:dev
```

浏览 `http://localhost:5173`。首次初始化只创建 `wrangler.self-host.json`，已有文件不会被覆盖。本地开发无需登录 Cloudflare，也无需创建数据库。

## 2. 配置自己的部署目标

编辑仓库根目录的 `wrangler.self-host.json`（合法 JSON，不添加注释）：

```json
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "your-agent-atlas",
  "main": "./worker/index.ts",
  "compatibility_date": "2026-05-22",
  "compatibility_flags": ["nodejs_compat"],
  "account_id": "YOUR_32_HEX_CLOUDFLARE_ACCOUNT_ID",
  "workers_dev": true,
  "preview_urls": false,
  "observability": { "enabled": true }
}
```

将 `name` 和 `account_id` 换成自己的。示例兼容日期匹配锁定依赖中本地 workerd 支持的日期；生产站点的兼容日期保持原值。升级 Wrangler/运行时后可在自己的实例重新验证并调整。这个文件被 Git 忽略，适合保存非秘密部署标识；**不要写 RPC 密钥或 API Token**。生产配置 `wrangler.jsonc` 留给维护者的站点，不要用它部署自己的实例。`self-host:*` 命令会拒绝维护者的 Worker 名、账户和域名，并核对构建后的目标配置。

当前只读页面/API 使用随仓库发布的 JSON/CSV，不需要 D1。生产仓库保留的 `DB` 绑定及迁移文件不会被自动用于你的实例；仅添加数据库不会启用写入接口。

## 3. 检查、构建与本地生产预览

Python 用于协议回归测试，不是网站运行时依赖：

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r scripts/activity/requirements.txt
python -m unittest discover -s tests -p 'test_*.py'
npm run check
npm run self-host:build
npm run self-host:preview
```

Windows 使用 `.venv\Scripts\activate` 激活环境。生产预览地址为 `http://127.0.0.1:8788`，使用 Wrangler 本地运行，不访问生产数据库。预览、dry-run 和 deploy 均重新构建，防止误用 `dist/` 中上一份生产构建；生成配置的 Worker、账户、域名和数据库绑定必须与本地配置相符。

## 4. 发布到自己的 Cloudflare

```sh
npx wrangler login
npx wrangler whoami
npm run self-host:dry-run
npm run self-host:deploy
```

确认 `whoami` 是自己的账户。部署前核对 [Cloudflare 当前限制](https://developers.cloudflare.com/workers/platform/limits/) 中的 Worker 大小、静态文件、CPU 和请求额度；数据会增长，dry-run 通过并不代表目标账户的所有配额均已验证。`dry-run` 只打包，`deploy` 才发布。首次部署可能需要启用自己的 workers.dev 子域名；以 Wrangler 返回的 URL 为准。每次部署都保留已有服务端变量，密钥由 Cloudflare 管理。无需部署者的钱包或签名，也不会执行链上交易。

如果要使用自定义域名，先在 Cloudflare 配置自己的域名，再将本地配置中的 `workers_dev` 设为 `false`，添加：

```json
"routes": [{ "pattern": "atlas.your-domain.example", "custom_domain": true }]
```

保留 `preview_urls: false`。不要填写维护者站点的域名。详见 [Cloudflare Custom Domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/)。

## 5. 可选 RPC

默认有公共 BSC RPC 回退。需要自己的服务时，使用服务端 secret：

```sh
npx wrangler secret put BSC_RPC_URL --config wrangler.self-host.json
```

在交互提示中输入地址，不要在命令行参数或日志中显示值。本地可复制 `.dev.vars.example` 为 `.dev.vars` 后填写 `BSC_RPC_URL`。不要使用 `NEXT_PUBLIC_` 或 `VITE_` 前缀，不要提交环境文件。

## 6. 验证上线

把下列路径中的域名换成 Wrangler 返回的自己的网址，逐项核对：

- `/`：目录、内外盘筛选、详情和每日注册图表（近 7 天 / 30 天 / 全部）。
- `/api/agents?size=1`、`/api/directory`、`/api/resolve?q=tagai.ai`。
- `/activity/manifest.json`、`/api/activity`：快照区块、追踪资产和数量。
- `/?view=holdings`、`/holdings/manifest.json`、`/api/holdings`：持仓时间和范围。
- `/holdings/registrations.json`、`/holdings/registrations.csv`：区块/hash 必须与持仓清单一致。
- 筛选、钱包历史、持有人分页及 CSV 下载；POST `/api/evidence` 应拒绝写入（403）。

构建或上传成功不等于公网核验成功。网络错误和 RPC 暂不可用应保留错误状态，不能视为零余额或未注册。

## 7. 更新代码与数据

拉取更新后重新执行检查和 `self-host:deploy`。内置快照可以直接展示；自行采集需要 [数据更新指南](DATA_UPDATES.md) 中的额外输入。

GitHub Actions 只执行检查；fork 不会继承维护者的 Workers Builds、桌面任务或凭据。如果自行连接 Workers Builds，设置安装命令 `npm ci --ignore-scripts --no-audit --no-fund`，构建命令 `npm run check && npm run self-host:build`，部署命令 `npm run self-host:deploy`；构建机器还必须在执行前创建自己的 `wrangler.self-host.json`。可由 CI 环境变量生成**非秘密**账户/域名配置，凭据通过 CI/Cloudflare 的 secrets 配置。未配置这一步时不要开启自动发布。

## 常见问题

- **配置缺失**：先运行 `npm run self-host:init`；在仓库根目录运行命令。
- **目标被拒绝**：填写自己的账户、Worker 和域名，不能复用维护者生产目标。
- **无法运行 npm/构建**：检查 Node 版本并重新 `npm ci --ignore-scripts --no-audit --no-fund`；保留原始构建错误用于排查。
- **Wrangler 登录过期**：重新 `npx wrangler login`，不绕过权限。
- **没有最新链上数据**：网页部署与数据采集是两件事；以快照截止时间为准。
