# 单元测试指南

> **与验证与评测体系（Evaluation）的关系**：
> - 单元测试本身就是 L1 程序化验证的重要载体之一（特别适合快速锁死规则解析、格式映射、校验与状态不变量）。
> - 本文档聚焦**如何写好单元测试**；项目整体的验证分层、载体映射（单测/集成/黑盒/评测/运行期脚本）与全生命周期演进规则见 [`docs/evaluation.md`](./evaluation.md)。

## 单元测试原则

- **拆分可测试逻辑**：长逻辑应拆分为职责单一的小函数，避免将文件 I/O、子进程调用与纯规则转换逻辑混在一处，确保每个函数独立可测。
- **优先使用 Table Driven Tests**：通过 `pytest.mark.parametrize` 以表格驱动的方式组织测试用例，将输入、期望输出统一定义为数据表，减少重复代码，便于扩展新用例。
- **无副作用（No Side Effects）**：单元测试不应依赖或修改仓库内的真实工作目录（如 `sources/`、`output/`）或依赖外部网络；需要文件系统时使用 pytest 内置 `tmp_path` fixture，保证测试可重复执行且结果稳定。
- **最小功能化**：每个测试只验证一个最小功能点，逐步积累覆盖，确保每层逻辑稳定后再向上组合。
- **不得无依据删减或降标**：既有单元测试不得在无需求/设计依据的情况下由 AI 自行删除、跳过或放宽断言；若因明确的需求或内部重构导致测试与新契约不一致，先对齐 spec / `evals/`（遵循 `project-stage`），再同步更新对应测试。

```python
import pytest


@pytest.mark.parametrize(
    ("name", "raw_rules", "expected"),
    [
        ("domain_suffix", [{"domain_suffix": ["example.com"]}], ["DOMAIN-SUFFIX,example.com"]),
        ("ip_cidr", [{"ip_cidr": ["1.1.1.0/24"]}], ["IP-CIDR,1.1.1.0/24"]),
    ],
)
def test_parse_rules(name, raw_rules, expected):
    ...
```

## 目录与命名规范

遵循 Python / pytest 默认惯例：

- 测试目录：`tests/`
- 测试文件：`tests/test_<module>.py`
- 测试函数：`def test_<behavior>():`

## 如何运行测试

```bash
# 运行全部测试
uv run pytest

# 运行单个测试文件
uv run pytest tests/test_<module>.py

# 按关键词筛选运行
uv run pytest -k <keyword>
```
