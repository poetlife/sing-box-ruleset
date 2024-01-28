# sing-box-ruleset
including singbox ruleset

原本的sing-box规则只能支持json配置，但是json配置起来太麻烦了，而且不支持注释，因此本repo收集一些规则集，并使用yaml进行标注，再转换成json配置的规则集，包含的规则如下：
- [`mainland-only`](https://github.com/poetlife/sing-box-ruleset/releases/latest/download/mainland-only.srs) 该部分规则集包含仅能再中国大陆访问的站点


##  compile-related

yaml to json
```bash
# 将rulesets文件中所有的yaml格式转换为json格式
python convert.py
```

compile rule to binary
```bash
sing-box rule-set compile config.json
```

## reference 
1. https://github.com/Chocolate4U/Iran-sing-box-rules/tree/main
2. https://github.com/Dreista/sing-box-rule-set-cn