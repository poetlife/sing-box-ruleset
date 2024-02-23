# sing-box-ruleset
including singbox ruleset

原本的sing-box规则只能支持json配置，但是json配置起来太麻烦了，而且不支持注释，因此本repo收集一些规则集，并使用yaml进行标注，再转换成json配置的规则集，包含的规则如下：
- [`mainland-only`](https://github.com/poetlife/sing-box-ruleset/releases/latest/download/mainland-only.srs) 该部分规则集包含仅能再中国大陆访问的站点
- [`proxy-only`](https://github.com/poetlife/sing-box-ruleset/releases/latest/download/proxy-only.srs) 该规则集包含一定需要proxy的站点

如果使用最新的[clash](https://wiki.metacubex.one/)，则可以使用下面的规则：
- [`mainland-only`](https://github.com/poetlife/sing-box-ruleset/releases/latest/download/clash-mainland-only.yaml) 该部分规则集包含仅能再中国大陆访问的站点
- [`proxy-only`](https://github.com/poetlife/sing-box-ruleset/releases/latest/download/clash-proxy-only.yaml) 该规则集包含一定需要proxy的站点
- [`cloudflare`](https://github.com/poetlife/sing-box-ruleset/releases/latest/download/cloudflare.yaml) 该规则包含了cloudflare的CDN的ip

##  compile-related

yaml to json and compile rule to binary
```bash
pip install -r requirements.txt
python convert.py
```

##  clash-verge-rev使用示例

```yaml
# 省略了节点等部分内容
rule-providers:
    mainland-only:
        behavior: classical
        interval: 259200
        type: http
        url: https://github.com/poetlife/sing-box-ruleset/releases/latest/download/clash-mainland-only.yaml
    proxy-only:
        behavior: classical
        interval: 259200
        type: http
        url: https://github.com/poetlife/sing-box-ruleset/releases/latest/download/clash-proxy-only.yaml
# 引用集合规则
rules:
    - RULE-SET,mainland-only,DIRECT
```

## reference 
1. https://github.com/Chocolate4U/Iran-sing-box-rules/tree/main
2. https://github.com/Dreista/sing-box-rule-set-cn
3. https://github.com/v2fly/domain-list-community