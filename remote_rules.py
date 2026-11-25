import ipaddress
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

import yaml
from loguru import logger

from rule_merger import merge_rules, normalize_rule_blocks

Fetcher = Callable[[str], str]

SUPPORTED_FORMATS = ("auto", "sing-box", "clash", "metacubex-list", "v2fly")

CLASH_TYPE_MAP = {
    "DOMAIN": "domain",
    "DOMAIN-SUFFIX": "domain_suffix",
    "DOMAIN-KEYWORD": "domain_keyword",
    "DOMAIN-REGEX": "domain_regex",
    "IP-CIDR": "ip_cidr",
    "IP-CIDR6": "ip_cidr6",
}

SINGBOX_RULE_KEYS = ("domain", "domain_suffix", "domain_keyword", "domain_regex", "ip_cidr")


def fetch_url(url: str, timeout: float = 15.0, retries: int = 2) -> str:
    """拉取远程文本内容，带超时与有限重试，失败时抛出异常。"""
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        start = time.monotonic()
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "sing-box-ruleset-compiler/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                if status < 200 or status >= 300:
                    raise RuntimeError(f"HTTP 状态异常 {status}: {url}")
                content = resp.read().decode("utf-8")
            elapsed = time.monotonic() - start
            logger.info(
                "拉取远程规则成功: url={url}, bytes={size}, elapsed={elapsed:.2f}s",
                url=url,
                size=len(content),
                elapsed=elapsed,
            )
            return content
        except urllib.error.HTTPError as exc:
            last_error = exc
            if 400 <= exc.code < 500:
                logger.error("拉取远程规则失败(客户端错误): url={url}, status={code}", url=url, code=exc.code)
                raise
            logger.warning(
                "拉取远程规则失败，准备重试({attempt}/{max_retries}): url={url}, status={code}",
                attempt=attempt + 1,
                max_retries=retries,
                url=url,
                code=exc.code,
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            logger.warning(
                "拉取远程规则网络异常({attempt}/{max_retries}): url={url}, error={err}",
                attempt=attempt + 1,
                max_retries=retries,
                url=url,
                err=exc,
            )
        if attempt < retries:
            time.sleep(0.5 * (attempt + 1))

    logger.error("拉取远程规则最终失败: url={url}, error={err}", url=url, err=last_error)
    raise RuntimeError(f"拉取远程规则失败: {url} ({last_error})") from last_error


def _classify_cidr(value: str) -> Optional[str]:
    if "/" not in value:
        return None
    try:
        net = ipaddress.ip_network(value, strict=False)
        return "ip_cidr6" if net.version == 6 else "ip_cidr"
    except ValueError:
        return None


def detect_format(content: str, url: str = "") -> str:
    """根据 URL 后缀与文本特征自动识别上游规则格式。"""
    stripped = content.lstrip()
    lower_url = url.lower().split("?", 1)[0]

    if lower_url.endswith(".json") or stripped.startswith("{"):
        return "sing-box"

    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith(("#", "//"))]
    if any(line.startswith("payload:") for line in lines):
        return "clash"
    for line in lines[:20]:
        candidate = line[2:].strip() if line.startswith("- ") else line
        prefix = candidate.split(",", 1)[0].strip().upper()
        if prefix in CLASH_TYPE_MAP or prefix in {"IP-ASN", "PROCESS-NAME", "USER-AGENT", "URL-REGEX", "DST-PORT"}:
            return "clash"

    if lower_url.endswith(".list") or any(line.startswith(("+.", ".")) for line in lines[:50]):
        return "metacubex-list"

    for line in lines[:50]:
        if line.startswith(("full:", "domain:", "keyword:", "regexp:", "include:")) or " @" in line:
            return "v2fly"

    return "v2fly"


def parse_singbox_rules(content: str) -> List[Dict[str, List[str]]]:
    data = json.loads(content)
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise ValueError("sing-box 规则 JSON 缺少有效的 rules 列表")

    parsed: List[Dict[str, List[str]]] = []
    for block in data["rules"]:
        if not isinstance(block, dict):
            continue
        for key in SINGBOX_RULE_KEYS:
            if key not in block:
                continue
            raw_val = block[key]
            values = raw_val if isinstance(raw_val, list) else [raw_val]
            if key == "ip_cidr":
                v4: List[str] = []
                v6: List[str] = []
                for item in values:
                    val = str(item).strip()
                    if not val:
                        continue
                    cidr_key = _classify_cidr(val)
                    if cidr_key == "ip_cidr6":
                        v6.append(val)
                    else:
                        v4.append(val)
                if v4:
                    parsed.append({"ip_cidr": v4})
                if v6:
                    parsed.append({"ip_cidr6": v6})
            else:
                cleaned = [str(v).strip() for v in values if str(v).strip()]
                if cleaned:
                    parsed.append({key: cleaned})
    return normalize_rule_blocks(parsed)


def parse_clash_rules(content: str) -> List[Dict[str, List[str]]]:
    lines: List[str] = []
    stripped = content.lstrip()
    has_payload_key = any(
        line.strip().startswith("payload:")
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
    if has_payload_key and not stripped.startswith(("DOMAIN", "IP-CIDR")):
        loaded = yaml.safe_load(content)
        if isinstance(loaded, dict) and isinstance(loaded.get("payload"), list):
            lines = [str(item).strip() for item in loaded["payload"] if item is not None]
        elif isinstance(loaded, list):
            lines = [str(item).strip() for item in loaded if item is not None]
        else:
            raise ValueError("Clash YAML 缺少有效的 payload 列表")
    else:
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line == "payload:":
                continue
            if line.startswith("- "):
                line = line[2:].strip()
            lines.append(line)

    parsed: List[Dict[str, List[str]]] = []
    skipped_types: Set[str] = set()
    for line in lines:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2:
            continue
        rule_type = parts[0].upper()
        value = parts[1]
        if not value:
            continue
        mapped = CLASH_TYPE_MAP.get(rule_type)
        if mapped:
            parsed.append({mapped: [value]})
        else:
            skipped_types.add(rule_type)

    if skipped_types:
        logger.warning("Clash 远程规则中跳过不支持的类型: {types}", types=sorted(skipped_types))
    return normalize_rule_blocks(parsed)


def parse_metacubex_list_rules(content: str) -> List[Dict[str, List[str]]]:
    parsed: List[Dict[str, List[str]]] = []
    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0].split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("+."):
            domain = line[2:].strip()
            if domain:
                parsed.append({"domain_suffix": [domain]})
        elif line.startswith("."):
            domain = line[1:].strip()
            if domain:
                parsed.append({"domain_suffix": [domain]})
        else:
            cidr_key = _classify_cidr(line)
            if cidr_key:
                parsed.append({cidr_key: [line]})
            else:
                parsed.append({"domain": [line]})
    return normalize_rule_blocks(parsed)


def _strip_v2fly_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _parse_v2fly_line(line: str) -> Tuple[Optional[str], List[str]]:
    tokens = line.split()
    if not tokens:
        return None, []
    entry = tokens[0]
    tags = [tok[1:] for tok in tokens[1:] if tok.startswith("@") and len(tok) > 1]
    return entry, tags


def _match_v2fly_tags(
    tags: List[str],
    exclude_tags: Set[str],
    include_tags: Set[str],
) -> bool:
    tag_set = set(tags)
    if exclude_tags and tag_set & exclude_tags:
        return False
    if include_tags and not (tag_set & include_tags):
        return False
    return True


def parse_v2fly_rules(
    content: str,
    source_url: str = "",
    fetcher: Optional[Fetcher] = None,
    exclude_tags: Optional[Iterable[str]] = None,
    include_tags: Optional[Iterable[str]] = None,
    _visited: Optional[Set[str]] = None,
) -> List[Dict[str, List[str]]]:
    active_fetcher = fetcher or fetch_url
    ex_tags = {t.lstrip("@").strip() for t in (exclude_tags or []) if t.strip()}
    in_tags = {t.lstrip("@").strip() for t in (include_tags or []) if t.strip()}
    visited = _visited if _visited is not None else set()
    if source_url:
        visited.add(source_url)

    parsed: List[Dict[str, List[str]]] = []
    for raw_line in content.splitlines():
        cleaned = _strip_v2fly_comment(raw_line)
        if not cleaned:
            continue
        entry, tags = _parse_v2fly_line(cleaned)
        if not entry:
            continue

        if entry.startswith("include:"):
            if ex_tags and set(tags) & ex_tags:
                continue
            target_name = entry[len("include:") :].strip()
            if not target_name:
                continue
            if not source_url:
                raise ValueError(f"v2fly include:{target_name} 缺少基准 source_url")
            include_url = urllib.parse.urljoin(source_url, target_name)
            if include_url in visited:
                continue
            visited.add(include_url)
            sub_content = active_fetcher(include_url)
            parsed.extend(
                parse_v2fly_rules(
                    sub_content,
                    source_url=include_url,
                    fetcher=active_fetcher,
                    exclude_tags=ex_tags,
                    include_tags=in_tags,
                    _visited=visited,
                )
            )
            continue

        if not _match_v2fly_tags(tags, ex_tags, in_tags):
            continue

        if entry.startswith("full:"):
            val = entry[len("full:") :].strip()
            if val:
                parsed.append({"domain": [val]})
        elif entry.startswith("domain:"):
            val = entry[len("domain:") :].strip()
            if val:
                parsed.append({"domain_suffix": [val]})
        elif entry.startswith("keyword:"):
            val = entry[len("keyword:") :].strip()
            if val:
                parsed.append({"domain_keyword": [val]})
        elif entry.startswith("regexp:"):
            val = entry[len("regexp:") :].strip()
            if val:
                parsed.append({"domain_regex": [val]})
        else:
            parsed.append({"domain_suffix": [entry]})

    return normalize_rule_blocks(parsed)


def parse_remote_content(
    content: str,
    fmt: str = "auto",
    source_url: str = "",
    fetcher: Optional[Fetcher] = None,
    exclude_tags: Optional[Iterable[str]] = None,
    include_tags: Optional[Iterable[str]] = None,
) -> List[Dict[str, List[str]]]:
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"不支持的远程规则格式: {fmt}，可选: {', '.join(SUPPORTED_FORMATS)}")

    resolved_fmt = detect_format(content, source_url) if fmt == "auto" else fmt
    logger.info("解析远程规则: url={url}, format={fmt}", url=source_url or "<inline>", fmt=resolved_fmt)

    if resolved_fmt == "sing-box":
        return parse_singbox_rules(content)
    if resolved_fmt == "clash":
        return parse_clash_rules(content)
    if resolved_fmt == "metacubex-list":
        return parse_metacubex_list_rules(content)
    return parse_v2fly_rules(
        content,
        source_url=source_url,
        fetcher=fetcher,
        exclude_tags=exclude_tags,
        include_tags=include_tags,
    )


def _filter_rule_blocks(
    blocks: List[Dict[str, List[str]]],
    exclude_values: Set[str],
    exclude_types: Set[str],
) -> List[Dict[str, List[str]]]:
    if not exclude_values and not exclude_types:
        return blocks

    filtered: List[Dict[str, List[str]]] = []
    for block in blocks:
        for key, vals in block.items():
            if key in exclude_types:
                continue
            kept = [val for val in vals if val not in exclude_values]
            if kept:
                filtered.append({key: kept})
    return filtered


def load_remote_rules(
    remote_specs: Optional[List[Dict[str, Any]]],
    fetcher: Optional[Fetcher] = None,
) -> List[Dict[str, List[str]]]:
    """拉取并解析 `remote_rules` 配置列表中的所有社区规则源，返回合并去重后的规则块列表。"""
    if not remote_specs:
        return []

    active_fetcher = fetcher or fetch_url
    all_blocks: List[List[Dict[str, List[str]]]] = []

    for spec in remote_specs:
        if not isinstance(spec, dict) or not spec.get("url"):
            raise ValueError(f"remote_rules 条目必须包含 url 字段: {spec}")
        url = str(spec["url"]).strip()
        fmt = str(spec.get("format", "auto")).strip()
        exclude_tags = spec.get("exclude_tags") or []
        include_tags = spec.get("include_tags") or []
        exclude_values = {str(v).strip() for v in (spec.get("exclude") or []) if str(v).strip()}
        exclude_types = {str(t).strip() for t in (spec.get("exclude_types") or []) if str(t).strip()}

        content = active_fetcher(url)
        blocks = parse_remote_content(
            content,
            fmt=fmt,
            source_url=url,
            fetcher=active_fetcher,
            exclude_tags=exclude_tags,
            include_tags=include_tags,
        )
        blocks = _filter_rule_blocks(blocks, exclude_values=exclude_values, exclude_types=exclude_types)
        summary = {k: len(v) for block in blocks for k, v in block.items()}
        logger.info("吸收远程规则完成: url={url}, summary={summary}", url=url, summary=summary)
        all_blocks.append(blocks)

    return merge_rules(*all_blocks)
