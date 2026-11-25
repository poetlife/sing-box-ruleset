# 远程社区规则吸收机制（remote_rules）

## 背景与目标

社区维护了大量高质量的规则库（如 `v2fly/domain-list-community`、`MetaCubeX/meta-rules-dat`、Clash Classical 规则集与 sing-box 规则源）。手工复制维护域名列表既容易遗漏新域名，也难以及时跟随上游更新。

本模块为 `rulesets/*.yml` 提供**编译期动态拉取、多格式解析与去重合并**机制：在规则 YAML 中通过 `remote_rules` 声明上游规则源后，`convert.py` 编译时自动拉取并吸收上游规则，与本地 `rules` 合并去重后统一输出为 sing-box（`.json` / `.srs`）与 Clash.Meta Classical（`.yaml`）产物。

## 行为契约

### 1. 规则源声明（向后兼容）

- 现有 `rulesets/*.yml` 中不配置 `remote_rules` 时，编译行为与产物结构保持完全兼容。
- 当配置 `remote_rules` 列表时，每个条目可声明上游地址（`url`）、可选格式（`format`，默认 `auto` 自动识别）、可选过滤条件（`exclude`、`exclude_types`、`exclude_tags`、`include_tags`）。

### 2. 支持的上游格式

1. **sing-box 规则源 JSON（`sing-box`）**：解析 `rules` 块中的 `domain`、`domain_suffix`、`domain_keyword`、`domain_regex`、`ip_cidr`（自动区分 IPv4/IPv6 CIDR，兼容单字符串与列表值）。
2. **Clash Classical 规则集（`clash`）**：解析 `payload` 列表或纯文本规则行中的 `DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-KEYWORD`、`DOMAIN-REGEX`、`IP-CIDR`、`IP-CIDR6`（自动剥离 `,no-resolve` 等附加参数；不支持的规则类型记日志跳过）。
3. **MetaCubeX / Mihomo 域名列表（`metacubex-list`）**：解析 `+.domain` / `.domain` 为 `domain_suffix`，裸域名为精确 `domain`，CIDR 为 `ip_cidr` / `ip_cidr6`，忽略注释与空行。
4. **v2fly domain-list-community（`v2fly`）**：支持裸域名与 `domain:`（`domain_suffix`）、`full:`（`domain`）、`keyword:`（`domain_keyword`）、`regexp:`（`domain_regex`），支持 `#` 行内注释、基于 `@tag` 的 `exclude_tags` / `include_tags` 过滤，以及同源 `include:` 递归展开与循环引用防护。

### 3. 合并、去重与输出映射

- 远程规则与本地 `rules` 合并时按规则类型聚合、保序去重，并剔除空规则项。
- **sing-box 规则集**输出支持 `domain`、`domain_suffix`、`domain_keyword`、`domain_regex`。
- **Clash.Meta Classical 规则集**输出支持 `DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-KEYWORD`、`DOMAIN-REGEX`、`IP-CIDR`、`IP-CIDR6`。

### 4. 失败语义与可观测性

- 远程规则拉取失败（网络错误、超时、非 2xx 状态）或格式解析失败时，必须记录 `ERROR` 日志并中断编译返回非零退出码，防止 CI 静默发布残缺规则集。
- 调用 `sing-box rule-set compile` 返回非零退出码时必须记录错误输出并中断；若本机未安装 `sing-box` CLI，记录 `WARNING` 并跳过 `.srs` 二进制编译。
- 关键路径需记录结构化日志：拉取 URL、格式、耗时、解析与去重后的规则条目摘要。

## 验证目标

| 目标 | 载体 | 验收标准 |
|------|------|----------|
| 多格式解析与过滤正确性 | `tests/test_remote_rules.py` | 4 种格式、自动识别、`include:` 递归与防环、`@tag`/`exclude` 过滤全部通过，无外部网络依赖 |
| 规则合并与去重不变量 | `tests/test_rule_merger.py` | 远程与本地规则合并保序去重、单值/列表规范化全部通过 |
| 端到端编译与错误语义 | `tests/test_convert.py` | 产物 JSON/YAML 结构符合契约，上游失败或编译失败显式报错，缺失 `sing-box` 降级告警 |
| 仓库全量检查与真实编译 | `uv run ruff check . && uv run pytest && uv run python convert.py` | Lint 与单元测试全绿；真实联网编译成功吸收社区 AI 规则集 |
