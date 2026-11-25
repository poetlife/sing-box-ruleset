from typing import Any, Dict, Iterable, List

RULE_TYPE_ORDER = (
    "domain",
    "domain_suffix",
    "domain_keyword",
    "domain_regex",
    "ip_cidr",
    "ip_cidr6",
)


def _normalize_values(raw_value: Any) -> List[str]:
    if raw_value is None:
        return []
    items = raw_value if isinstance(raw_value, list) else [raw_value]
    normalized: List[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def normalize_rule_blocks(raw_rules: Iterable[Dict[str, Any]] | None) -> List[Dict[str, List[str]]]:
    """将松散的规则块列表规范化为去重后的 `{rule_type: [values]}` 列表。"""
    if not raw_rules:
        return []

    buckets: Dict[str, Dict[str, None]] = {}
    extra_keys: List[str] = []

    for block in raw_rules:
        if not isinstance(block, dict):
            raise ValueError(f"规则条目必须为字典类型，实际为: {type(block).__name__}")
        for key, raw_val in block.items():
            values = _normalize_values(raw_val)
            if not values:
                continue
            if key not in buckets:
                buckets[key] = {}
                if key not in RULE_TYPE_ORDER:
                    extra_keys.append(key)
            for val in values:
                buckets[key][val] = None

    ordered_keys = [k for k in RULE_TYPE_ORDER if k in buckets] + extra_keys
    return [{key: list(buckets[key].keys())} for key in ordered_keys]


def merge_rules(*rule_lists: Iterable[Dict[str, Any]] | None) -> List[Dict[str, List[str]]]:
    """按规则类型合并多个规则列表并保序去重。"""
    combined: List[Dict[str, Any]] = []
    for rule_list in rule_lists:
        if rule_list:
            combined.extend(rule_list)
    return normalize_rule_blocks(combined)
