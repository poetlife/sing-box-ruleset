import yaml
import json
import os
import subprocess

from typing import List, Dict
from loguru import logger


class CommonRuleSet:
    """通用的规则集"""

    allow_rules: Dict[str, str] = {}  # 允许的规则转换

    extra_fields: Dict = {}  # 额外需要的字段

    rules_key: str = "rules"

    def __init__(self) -> None:
        self.rules: List[str] = []
        self.allow_keys: List[str] = [i for i, _ in self.allow_rules.items()]

        logger.info(
            "{name}允许转换的键值: {keys}",
            keys=self.allow_keys,
            name=self.__class__.__name__,
        )

    def parse_rules(self, rules: List[Dict[str, List]]):
        """解析规则"""
        for rule in rules:
            for key, vals in rule.items():
                if key in self.allow_keys:
                    self.rules.append({self.allow_rules[key]: vals})
                else:
                    logger.info(
                        "{name}不包含规则集{rule}",
                        name=self.__class__.__name__,
                        rule=key,
                    )

    def to_dict(self) -> Dict:
        tmp = self.extra_fields.copy()
        tmp[self.rules_key] = self.rules
        return tmp

    def to_json(self, path: str):
        raise NotImplementedError

    def to_yaml(self, path: str):
        raise NotImplementedError

    def to_binary(self, path: str):
        raise NotImplementedError


class SingBoxRuleSet(CommonRuleSet):
    """sing-box规则集"""

    allow_rules = {"domain_suffix": "domain_suffix"}
    extra_fields = {"version": 1}

    def to_json(self, path: str):
        logger.info(
            "{name}导出为json文件：{file}", name=self.__class__.__name__, file=path
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def to_binary(self, source_path: str, dst_path: str):
        logger.info(
            "{name}导出为sing-box二进制ruleset文件：{source} - {dst}",
            name=self.__class__.__name__,
            source=source_path,
            dst=dst_path,
        )
        self.to_json(source_path)
        subprocess.run(
            f"sing-box rule-set compile {source_path} -o {dst_path} ", shell=True
        )


class ClassicalClashRuleSet(CommonRuleSet):
    """Clash.Meta Classical规则集"""

    allow_rules = {
        "domain_suffix": "DOMAIN-SUFFIX",
        "ip_cidr": "IP-CIDR",
        "ip_cidr6": "IP-CIDR6",
    }

    rules_key = "payload"

    def parse_rules(self, rules: List[Dict[str, List]]):
        """解析规则"""
        for rule in rules:
            for key, vals in rule.items():
                if key in self.allow_keys:
                    for val in vals:
                        self.rules.append(f"{self.allow_rules[key]},{val}")
                else:
                    logger.info(
                        "{name}不包含规则集{rule}",
                        name=self.__class__.__name__,
                        rule=key,
                    )

    def to_yaml(self, path: str):
        logger.info(
            "{name}导出为yaml文件：{file}", name=self.__class__.__name__, file=path
        )
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f)


def mkdir(name):
    if os.path.exists(name):
        return
    else:
        os.mkdir(name)


if __name__ == "__main__":
    """将rulesets中所有yaml的文件都转换为json格式存入到sources中去"""
    mkdir("sources")
    mkdir("output")
    for root, dirs, files in os.walk("rulesets"):
        for file in files:
            path = os.path.join(root, file)
            _, extension = os.path.splitext(path)
            # print(filename, extension)
            file = file.replace(extension, "")
            source = f"sources/{file}.json"
            output = f"output/{file}.srs"

            if extension in [".yml", ".yaml"]:
                # 编译成sing-box规则
                # convert_yaml_to_json(path, source)
                logger.info("处理文件：{file}", file=file)
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                # 处理clash.meta规则
                if data.get("clash", False):
                    clash_rule = ClassicalClashRuleSet()
                    clash_rule.parse_rules(data.get("rules"))
                    clash_rule.to_yaml(f"output/clash-{file}.yaml")

                if data.get("sing-box", False):
                    singbox_rule = SingBoxRuleSet()
                    singbox_rule.parse_rules(data.get("rules"))
                    singbox_rule.to_binary(source_path=source, dst_path=output)
