import yaml
import json
import os
import subprocess

from typing import List


class ClassicalClashRuleSet:
    def __init__(self) -> None:
        self.rules: List[str] = []

    def add_domain_suffix_rule(self, content: str):
        self.rules.append(f"DOMAIN-SUFFIX,{content}")

    def batch_add_domain_suffix_rule(self, contents: List[str]):
        for i in contents:
            self.add_domain_suffix_rule(i)

    def to_clash_dict(self) -> dict:
        tmp = {"payload": self.rules}
        return tmp

    def to_yaml_file(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_clash_dict(), f)

    def from_singbox_rules(self, rules: dict, path: str = ""):
        if path != "" and rules is None:
            with open(path, "r", encoding="utf-8") as yaml_stream:
                rules = yaml.safe_load(yaml_stream)

        if rules.get("version") != 1:
            raise ValueError("sing-box规则版本不为1")
        rulesets = rules.get("rules")
        if rulesets != None:
            for ruleset in rulesets:
                if isinstance(ruleset, dict):
                    for key, val in ruleset.items():
                        if key == "domain_suffix":
                            self.batch_add_domain_suffix_rule(val)
                        else:
                            raise ValueError(f"不支持的规则类型{key}")


def convert_yaml_to_json(yaml_file, json_file):
    with open(yaml_file, "r", encoding="utf-8") as yaml_stream:
        # 解析 YAML 文件
        yaml_data = yaml.safe_load(yaml_stream)

    # 将 Python 对象转换为 JSON 格式
    json_data = json.dumps(yaml_data, indent=2)

    # 将 JSON 数据写入文件
    with open(json_file, "w", encoding="utf-8") as json_stream:
        json_stream.write(json_data)


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
                convert_yaml_to_json(path, source)
                subprocess.run(
                    f"sing-box rule-set compile {source} -o {output} ", shell=True
                )
                # 编译成clash规则
                tmp_clash_rule = ClassicalClashRuleSet()
                tmp_clash_rule.from_singbox_rules(None, path=path)
                tmp_clash_rule.to_yaml_file(
                    f"output/clash-{file}.yaml"
                )
