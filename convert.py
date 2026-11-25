import json
import os
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger

from remote_rules import Fetcher, load_remote_rules
from rule_merger import merge_rules


class CommonRuleSet:
    """通用的规则集"""

    allow_rules: Dict[str, str] = {}  # 允许的规则转换

    extra_fields: Dict[str, Any] = {}  # 额外需要的字段

    rules_key: str = "rules"

    def __init__(self) -> None:
        self.rules: List[Any] = []
        self.allow_keys: List[str] = list(self.allow_rules.keys())

        logger.info(
            "{name}允许转换的键值: {keys}",
            keys=self.allow_keys,
            name=self.__class__.__name__,
        )

    def parse_rules(self, rules: List[Dict[str, List[str]]]):
        """解析规则"""
        for rule in rules:
            for key, vals in rule.items():
                if key in self.allow_keys:
                    self.rules.append({self.allow_rules[key]: vals})
                else:
                    logger.warning(
                        "{name}不包含规则集{rule}",
                        name=self.__class__.__name__,
                        rule=key,
                    )

    def to_dict(self) -> Dict[str, Any]:
        tmp = self.extra_fields.copy()
        tmp[self.rules_key] = self.rules
        return tmp

    def to_json(self, path: str):
        raise NotImplementedError

    def to_yaml(self, path: str):
        raise NotImplementedError

    def to_binary(self, source_path: str, dst_path: str):
        raise NotImplementedError


class SingBoxRuleSet(CommonRuleSet):
    """sing-box规则集"""

    allow_rules = {
        "domain": "domain",
        "domain_suffix": "domain_suffix",
        "domain_keyword": "domain_keyword",
        "domain_regex": "domain_regex",
    }
    extra_fields = {"version": 1}

    def to_json(self, path: str):
        logger.info("{name}导出为json文件：{file}", name=self.__class__.__name__, file=path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def to_binary(self, source_path: str, dst_path: str):
        logger.info(
            "{name}导出为sing-box二进制ruleset文件：{source} - {dst}",
            name=self.__class__.__name__,
            source=source_path,
            dst=dst_path,
        )
        self.to_json(source_path)

        sing_box_bin = shutil.which("sing-box")
        if not sing_box_bin:
            logger.warning("未检测到 sing-box CLI，跳过二进制编译: {dst}", dst=dst_path)
            return

        cmd = [sing_box_bin, "rule-set", "compile", source_path, "-o", dst_path]
        start = time.monotonic()
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        elapsed = time.monotonic() - start
        if result.returncode != 0:
            logger.error(
                "sing-box 编译失败: cmd={cmd}, exit_code={code}, elapsed={elapsed:.2f}s, stderr={stderr}",
                cmd=" ".join(cmd),
                code=result.returncode,
                elapsed=elapsed,
                stderr=result.stderr.strip(),
            )
            raise RuntimeError(f"sing-box 编译失败 (exit={result.returncode}): {result.stderr.strip()}")
        logger.info(
            "sing-box 编译成功: dst={dst}, elapsed={elapsed:.2f}s",
            dst=dst_path,
            elapsed=elapsed,
        )


class ClassicalClashRuleSet(CommonRuleSet):
    """Clash.Meta Classical规则集"""

    allow_rules = {
        "domain": "DOMAIN",
        "domain_suffix": "DOMAIN-SUFFIX",
        "domain_keyword": "DOMAIN-KEYWORD",
        "domain_regex": "DOMAIN-REGEX",
        "ip_cidr": "IP-CIDR",
        "ip_cidr6": "IP-CIDR6",
    }

    rules_key = "payload"

    def parse_rules(self, rules: List[Dict[str, List[str]]]):
        """解析规则"""
        for rule in rules:
            for key, vals in rule.items():
                if key in self.allow_keys:
                    for val in vals:
                        self.rules.append(f"{self.allow_rules[key]},{val}")
                else:
                    logger.warning(
                        "{name}不包含规则集{rule}",
                        name=self.__class__.__name__,
                        rule=key,
                    )

    def to_yaml(self, path: str):
        logger.info("{name}导出为yaml文件：{file}", name=self.__class__.__name__, file=path)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True)


def mkdir(name: str):
    os.makedirs(name, exist_ok=True)


def compile_ruleset_file(
    path: str,
    sources_dir: str = "sources",
    output_dir: str = "output",
    fetcher: Optional[Fetcher] = None,
) -> Dict[str, Any]:
    """解析单个规则集 YAML（含 remote_rules 与本地 rules）并编译导出对应产物。"""
    filename = os.path.basename(path)
    name, _ = os.path.splitext(filename)
    source = os.path.join(sources_dir, f"{name}.json")
    output = os.path.join(output_dir, f"{name}.srs")
    clash_output = os.path.join(output_dir, f"clash-{name}.yaml")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    enable_clash = bool(data.get("clash", False))
    enable_singbox = bool(data.get("sing-box", False))
    remote_specs = data.get("remote_rules") or []
    local_rules = data.get("rules") or []

    logger.info(
        "处理文件：{file} (sing-box={singbox}, clash={clash}, remote_sources={remote_count})",
        file=name,
        singbox=enable_singbox,
        clash=enable_clash,
        remote_count=len(remote_specs),
    )

    remote_rules = load_remote_rules(remote_specs, fetcher=fetcher)
    merged_rules = merge_rules(remote_rules, local_rules)
    rule_summary = {k: len(v) for block in merged_rules for k, v in block.items()}
    logger.info("规则合并去重完成：{file}, summary={summary}", file=name, summary=rule_summary)

    if enable_clash:
        clash_rule = ClassicalClashRuleSet()
        clash_rule.parse_rules(merged_rules)
        clash_rule.to_yaml(clash_output)

    if enable_singbox:
        singbox_rule = SingBoxRuleSet()
        singbox_rule.parse_rules(merged_rules)
        singbox_rule.to_binary(source_path=source, dst_path=output)

    return {
        "name": name,
        "sing-box": enable_singbox,
        "clash": enable_clash,
        "summary": rule_summary,
    }


def compile_all(
    rulesets_dir: str = "rulesets",
    sources_dir: str = "sources",
    output_dir: str = "output",
    fetcher: Optional[Fetcher] = None,
) -> List[Dict[str, Any]]:
    """编译目录下全部规则集文件。"""
    mkdir(sources_dir)
    mkdir(output_dir)
    results: List[Dict[str, Any]] = []

    for root, _, files in os.walk(rulesets_dir):
        for file in sorted(files):
            path = os.path.join(root, file)
            _, extension = os.path.splitext(path)
            if extension.lower() in [".yml", ".yaml"]:
                results.append(
                    compile_ruleset_file(
                        path=path,
                        sources_dir=sources_dir,
                        output_dir=output_dir,
                        fetcher=fetcher,
                    )
                )
    return results


if __name__ == "__main__":
    compile_all()
