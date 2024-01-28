import yaml
import json
import os
import subprocess

def convert_yaml_to_json(yaml_file, json_file):
    with open(yaml_file, 'r', encoding="utf-8") as yaml_stream:
        # 解析 YAML 文件
        yaml_data = yaml.safe_load(yaml_stream)

    # 将 Python 对象转换为 JSON 格式
    json_data = json.dumps(yaml_data, indent=2)

    # 将 JSON 数据写入文件
    with open(json_file, 'w', encoding="utf-8") as json_stream:
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
            source = f"sources/{file}.json"
            output = f"output/{file}.srs"

            if extension in [".yml", ".yaml"]:
                convert_yaml_to_json(path, source)
                subprocess.run(f"sing-box rule-set compile {source} -o {output} ", shell=True)
