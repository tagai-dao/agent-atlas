# 数据采集与更新

## 直接使用快照

`data/`、`public/activity/` 和 `public/holdings/` 包含可直接部署的数据。全站功能无需原始缓存即可运行。`data/research.json` 和各 manifest 记录实际时间、区块、范围及数量，不把复制快照当成重新采集。

## 自行维护的前提

需要 Python 3.11+，安装 `scripts/activity/requirements.txt`。X 图片识别可使用 macOS Vision 或自行安装的 Tesseract；缺少 OCR 或原图时保留待补证状态，不把缺失识别结果当作否定证据。所有原始输出放在仓库外；`.sync-state`、RPC 环境文件、X 登录状态和原始研究缓存不能公开发布。维护者本机的自动化、私有路径和原始缓存不随仓库提供。

活动刷新是**增量采集器**，必须提供先前完整的原始活动快照（含事件源、发送者缓存、身份、池校验及 `refresh-complete.json`）。发布后的 JSON/CSV 不是原始基线，不能转换为空事件基线来冒充完整回补。新维护者必须从可信来源取得并验证完整原始基线，或自行实现并核验从合约部署区块开始的完整回补；本仓库没有提供一键活动 bootstrap 下载。这不妨碍部署和使用已发布快照。

持仓首次采集不需要原始基线：脚本从实际 registry 部署区块 `127950748` 重放全部 ERC721 Transfer，包括转移和销毁，再查询当前注册钱包。需要能读取该历史区间的 BSC RPC；首次运行可能耗时较长。失败时保留缓存，不跳过早期区块。

## 活动、NFT、持仓与注册图表的联合更新

在专用工作区操作，先确认没有其他同步、未提交的人工修改或待发布任务。安全地设置进程环境 `BSC_RPC_URL`，或对持仓脚本使用 `--rpc-env-file /path/to/private.env --rpc-env-name BSC_RPC_URL`；该文件只被解析，不执行 `source`。

以下变量是操作者填写的路径，不能照抄成维护者的机器路径：

```sh
python scripts/activity/refresh.py --source /path/to/verified-activity-raw --out /path/to/new-activity-raw
python scripts/activity/normalize.py /path/to/new-activity-raw
python scripts/holdings/refresh.py --source /path/to/verified-holdings-raw --out /path/to/new-holdings-raw
python scripts/holdings/normalize.py /path/to/new-holdings-raw
```

首次持仓采集省略其 `--source`。活动归一化先生成本轮追踪资产，再让持仓采集读取这些实际 ERC20；如果后续持仓失败，不发布已修改的活动数据。持仓范围只包括 BNB、网站追踪的实际 ERC20 和 Relic 当前 balanceOf，不包含曲线份额、未领取份额或 DeFi 仓位。

每类快照独立固定区块并记录 hash，全部依赖合约读取、分页与重试使用该固定区块的 Multicall3。验证完整标记与 anchor 匹配后才归一化。不得用普通 Transfer 推断成交，不得将历史铸造数量当持仓。Flap 只自动收录链上核验满足 DEX 条件且池协议受支持的代币；同名资产按完整 CA 区分。

持仓 refresh 同时从完整注册事件生成 `registration-history.json`，normalize 发布注册 JSON/CSV。北京时间自然日、首次 mint 去重、零注册日及未完整的最后一天必须保留，不能复制上一轮图表冒充新快照。

完成两部分采集后执行：

```sh
python -m unittest discover -s tests -p 'test_*.py'
npm run check
npm run self-host:dry-run
```

比较新增/移除成交、身份、余额及 NFT 数量，核对 AIPRO legacy buy/sell/tradeCount 与账本一致。仅提交预期数据变化，部署到自己的实例，按部署教程验证 API、分片、CSV 与 manifest 一致。成功后再原子更新自己的原始基线指针；失败时保留旧基线、完整缓存、待发布 commit 和部署结果，不重复提交相同快照。

## X 证据独立更新

需要自行维护授权来源文件，格式与现有 `mappings_v2.json` 导入契约一致：

```sh
python scripts/import-local.py --source /path/to/mappings_v2.json --review-cache /path/to/public-review-cache
python -m unittest discover -s tests -p 'test_*.py'
npm run check
```

导入按源指纹去重，保留人工状态、来源评级、清理与隔离，并在固定 BSC 区块核验名称。先补读完整原帖/文章及内嵌图，复用原图 OCR；资料不足标待补证，不强行降为弱线索。单一自身身份图和显示名中的对应 `.ai` 为最强关联，多个 `.ai` 名称的图片不采用图片关联。X 关联不是钱包控制权证明。

X 更新不得改动活动、NFT、持仓及注册统计的区块、时间或数据；检查这些文件的 hash 未变。执行部署与公网验证后才标记来源成功。部署者需要自行安排定时 runner 和串行锁；维护者的六小时 X / 两小时链上任务不自动移植到 fork。不要同时启动两轮全量持仓采集，不要无限重试或擅自扩展付费额度。
