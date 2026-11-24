# 可观测性总览

本文档描述本项目可观测性基础设施的接入方式与使用规范。

## 日志（Logging）

- 框架：`loguru`（已在 `convert.py` 中接入）
- 格式：
  - 控制台：人类可读的纯文本（含时间戳、级别、消息）
  - 文件（如需落盘审计或 CI 归档）：结构化 JSON，每行一条记录（JSON Lines，通过 `logger.add(..., serialize=True)` 启用）
- JSON Schema（文件输出字段定义）：
  ```json
  {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["timestamp", "level", "message", "trace_id"],
    "properties": {
      "timestamp": { "type": "string", "format": "date-time", "description": "ISO 8601 UTC 时间" },
      "level":     { "type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] },
      "message":   { "type": "string" },
      "logger":    { "type": "string", "description": "logger 名称 / 模块路径" },
      "trace_id":  { "type": "string", "description": "链路追踪 ID，用于串联同一批次/请求的事件链" },
      "extra":     { "type": "object", "description": "业务自定义字段，任意键值对" }
    }
  }
  ```
- 级别约定：ERROR=需要立即处理的故障（如 YAML 解析失败、`sing-box` 编译返回非零退出码）；WARN=可恢复的异常（如规则中出现目标格式不支持而被忽略的键）；INFO=关键业务事件（处理文件、导出产物路径）；DEBUG=开发调试

### 关键路径日志链路设计

关键路径的日志必须形成可追溯的完整链路，避免故障复盘时出现"日志断点"。设计原则：

- **以排障记录为输入**：定期回顾 [`docs/debugging/registry.md`](./debugging/registry.md) 中反复出现的症状，识别那些"日志缺失/不足导致定位耗时"的故障类型，把这些路径列为关键路径。
- **关键路径的判定**：满足以下任一条件即视为关键路径，必须设计完整日志链路：
  - 在 debug registry 中出现过 ≥2 次同类症状
  - 涉及外部依赖调用（如 `sing-box rule-set compile` 子进程、外部数据源拉取）
  - 涉及不可逆发布或产物覆盖操作（如 GitHub Releases 发布与旧版本清理）
  - 跨服务/跨进程的调用链路
- **完整链路的最低要求**：
  - **入口日志**：记录编译批次或单个规则文件开始处理时的输入路径与目标格式开关（`sing-box` / `clash`）
  - **关键决策点**：忽略不支持的规则键、跳过未启用格式等分支需明确日志记录
  - **外部调用**：调用 `sing-box` 子进程前记录命令与输入/输出路径，调用后记录退出码、耗时与错误输出
  - **异常出口**：所有异常分支必须记录 ERROR 日志、上下文（规则文件名、规则键）与堆栈
  - **正常出口**：记录导出产物路径与规则条目摘要
- **trace_id 传递**：单次批处理或跨步骤流转时通过统一上下文标识串联日志（服务形态下通过 `X-Trace-Id` Header 透传）。
- **闭环机制**：每次新增一条排障记录到 [`docs/debugging/records/`](./debugging/records/) 时，在"预防措施"小节明确补充：本次故障对应的关键路径是否已具备完整日志？若否，本次修复必须同步补齐日志埋点。

## 指标（Metrics）

> 本项目当前为离线批量规则编译 CLI 工具，无常驻服务进程与指标暴露端点。如后续演进为常驻服务或统计任务，遵循以下约定：

- 命名规范：`sing_box_ruleset_<module>_<metric>_<unit>`
- 推荐采集的基础指标：编译规则集总数、规则条目数、编译失败率、编译耗时

## 链路追踪（Tracing）

> 当前为单进程 CLI + 子进程编译形态，暂不接入分布式链路追踪。如后续演进为跨服务调用，接入 OpenTelemetry 并通过 HTTP Header `X-Trace-Id` 传播 TraceID。

## 健康检查

> 当前为离线批处理仓库，不暴露 HTTP 健康检查端点；CI 编译与产物校验入口见 [`docs/evaluation.md`](./evaluation.md)。如后续提供 HTTP 服务，统一暴露 `GET /health` 返回 `{"status": "ok"}`。
