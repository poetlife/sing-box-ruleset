# sing-box-ruleset

## 项目概览

收集并维护带注释的 YAML 规则集（`rulesets/*.yml`），通过 Python 脚本（`convert.py`）编译为 **sing-box** 规则源 JSON（`sources/*.json`）与二进制 `.srs`（`output/*.srs`），以及 **Clash.Meta / Mihomo** Classical 规则集 YAML（`output/clash-*.yaml`），并在推送 Git Tag 时由 GitHub Actions 自动发布至 GitHub Releases。

### 仓库结构与常用命令

- `rulesets/`：带注释的 YAML 规则源文件（如 `mainland-only.yml`、`proxy-only.yml`、`cloudflare.yml`）
- `convert.py`：规则解析、格式转换与调用 `sing-box rule-set compile` 的主脚本
- `sources/`、`output/`：编译期生成目录（已在 `.gitignore` 忽略）
- `.github/workflows/release.yml`：CI 编译与 Tag 自动发布流程（保留最近 5 个 release/tag）
- `pyproject.toml` / `requirements.txt`：Python 依赖与 ruff 代码规范配置（现有 CI 仍兼容 `requirements.txt`）

```bash
# 安装依赖（uv）
uv sync

# 编译全部规则集（需本机安装 sing-box CLI 以生成 .srs）
uv run python convert.py

# 代码规范检查与测试
uv run ruff check .
uv run pytest
```

## 项目阶段

**project-stage:** `confirm`

破坏性变化须先说明影响面和迁移方式，得到用户明确确认后再改。未确认前只做兼容改动。

破坏性变化：使既有调用方、持久化数据或既有操作步骤无法原样继续工作的改动。包括删除、重命名或收紧对外行为（API、CLI、配置键、事件、错误语义），改变已有数据的格式或含义，搬迁或删除已有公共入口。只增不改的扩展、对外行为不变的内部替换、补文档，以及把行为修回 spec 的缺陷修复，不是破坏性变化。

## 文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 可观测性总览 | [docs/observability.md](docs/observability.md) | 日志、指标、追踪的接入方式与规范 |
| 验证与评测指南 | [docs/evaluation.md](docs/evaluation.md) | 需求验证目标的形式化、程序化规范与全生命周期回归入口 |
| 单元测试指南 | [docs/testing.md](docs/testing.md) | 单元测试原则、目录规范与运行命令 |
| SSOT 注册表 | [docs/ssot-registry.md](docs/ssot-registry.md) | 同一件事唯一入口的登记表 |
| 历史排障记录 | [docs/debugging/registry.md](docs/debugging/registry.md) | 查问题前先检索同质症状 |
| 持续进化索引 | [docs/evolution/registry.md](docs/evolution/registry.md) | 从事实数据到改进验证的跨周期状态 |

> 功能设计文档位于 `docs/design/`，每个模块一个文件；程序化验证载体与运行入口统一索引于 `docs/evaluation.md`。新增模块时在此表格追加一行。

## 开发规范

- spec 是功能行为的唯一信源；代码是实现的唯一信源；程序化验证资产（单测、集成测试、黑盒/E2E 或 `evals/`，见 `docs/evaluation.md`）是全生命周期的自动化裁判
- spec（`docs/design/`）中只描述"做什么"、"为什么"与验证目标契约，不描述函数签名、数据结构或算法步骤
- **验证贯穿全生命周期（目标前置 + 对话纠偏沉淀）**：提需求或改需求时先对齐已知验证目标；行为变更先更新 spec 与对应程序化验证再改代码；与 AI 对话协作中每当用户纠正错误逻辑或锁死某项约束，当场沉淀为程序化验证用例，不靠聊天记忆维持正确性
- **验证资产演进边界**：需求不变时（重构、内部优化），既有验证为只读回归裁判，全量通过即自动证明未破坏行为；需求变更需调整既有断言时，遵循「项目阶段」的 `project-stage` 规则同步演化 spec 与验证用例；任何阶段严禁无需求依据地删减、跳过或放宽既有验证
- **排障与进化必须沉淀回归**：故障修复与线上进化改进落地时，必须同步沉淀可复跑的回归验证用例，防止复发
- 能否破坏既有契约（含既有验证断言），以「项目阶段」的 `project-stage` 为准

## 模块化设计原则

AI 辅助开发时代，代码生成速度远超人工 review 速度。良好的模块化是让代码库保持可理解、可审查的关键防线。

**目录结构即架构**：目录层级应反映职责边界，而不是随意堆放。新建文件前先想清楚它属于哪个模块，放错位置比命名错误更难纠正。

**文件名必须有实际意义**：
- 文件名应能独立表达其职责，不依赖上下文才能理解
- 避免：`utils.ts`、`helper.py`、`common.java`、`misc/`
- 推荐：`order-validator.ts`、`payment_gateway.py`、`RetryPolicy.java`

**单一职责**：一个文件只做一件事。文件开始"又做 A 又做 B"时，是拆分的信号，而不是继续往里加的理由。

**依赖方向显式化**：模块间依赖应单向、可见。循环依赖是模块边界划错的症状，发现时应重新审视边界，而不是绕开它。

## Single Source of Truth 原则

同一件事在整个仓库里**必须只有一个事实标准来源**。优先级高于"就近实现"和"临时便捷"。

判定标准（满足任意一条就视为"同一件事"）：

- 同一个**判断**（例：某工具是否可用、某资源是否存在、某版本是否符合要求）
- 同一次**加载 / 合并 / 规范化**（例：读取并合并配置、规范化字段、解析引用）
- 同一类**副作用**（例：写结构化日志、发通知、apply 资源）
- 同一个**数据源**（例：服务映射、配置清单、状态数据）

禁止行为：

- 脚本 A 用方法 1 做了判断，脚本 B 做**同样**判断时另写方法 2（即使"两行就搞定"）
- 把公共函数复制一份做"轻微定制"，而不是回流到公共模块
- 文档里就同一件事给出与代码实现不一致的描述

改动前必做：

1. 查 [`docs/ssot-registry.md`](docs/ssot-registry.md)，确认要做的判断 / 操作 / 数据读取是否已有登记
2. 已登记 → 直接复用；需求不满足时改那一个入口，不得在调用侧绕开
3. 未登记但会跨模块复用 → 抽到公共模块后**在注册表里登记一行**
