import json

import pytest

from remote_rules import detect_format, load_remote_rules, parse_remote_content


@pytest.mark.parametrize(
    ("name", "url", "content", "expected_fmt"),
    [
        ("json_ext", "https://example.com/openai.json", '{"version": 2, "rules": []}', "sing-box"),
        ("json_body", "https://example.com/rules", '  {"version": 1, "rules": []}', "sing-box"),
        ("clash_yaml", "https://example.com/ai.yaml", "payload:\n  - DOMAIN-SUFFIX,openai.com\n", "clash"),
        (
            "clash_plain",
            "https://example.com/ai.txt",
            "DOMAIN,api.openai.com\nIP-CIDR,1.1.1.0/24,no-resolve\n",
            "clash",
        ),
        ("metacubex_list", "https://example.com/openai.list", "+.openai.com\napi.openai.com\n", "metacubex-list"),
        ("v2fly_prefixes", "https://example.com/data/openai", "openai.com\nfull:api.openai.com\n", "v2fly"),
        ("v2fly_tags", "https://example.com/data/openai", "openai.com @cn\n", "v2fly"),
    ],
)
def test_detect_format(name, url, content, expected_fmt):
    assert detect_format(content, url=url) == expected_fmt


@pytest.mark.parametrize(
    ("name", "fmt", "content", "expected"),
    [
        (
            "singbox_json_v2",
            "sing-box",
            json.dumps(
                {
                    "version": 2,
                    "rules": [
                        {
                            "domain": ["api.openai.com"],
                            "domain_suffix": ["openai.com", "chatgpt.com"],
                            "domain_regex": "^chatgpt-.*\\.azure\\.com$",
                            "ip_cidr": ["1.1.1.0/24", "2400:cb00::/32"],
                        }
                    ],
                }
            ),
            [
                {"domain": ["api.openai.com"]},
                {"domain_suffix": ["openai.com", "chatgpt.com"]},
                {"domain_regex": ["^chatgpt-.*\\.azure\\.com$"]},
                {"ip_cidr": ["1.1.1.0/24"]},
                {"ip_cidr6": ["2400:cb00::/32"]},
            ],
        ),
        (
            "clash_yaml_with_unsupported",
            "clash",
            """
payload:
  - DOMAIN,browser-intake-datadoghq.com
  - DOMAIN-SUFFIX,openai.com
  - DOMAIN-KEYWORD,chatgpt
  - DOMAIN-REGEX,^sora\\.com$
  - IP-CIDR,104.16.0.0/13,no-resolve
  - IP-CIDR6,2606:4700::/32,no-resolve
  - IP-ASN,13335,no-resolve
""",
            [
                {"domain": ["browser-intake-datadoghq.com"]},
                {"domain_suffix": ["openai.com"]},
                {"domain_keyword": ["chatgpt"]},
                {"domain_regex": ["^sora\\.com$"]},
                {"ip_cidr": ["104.16.0.0/13"]},
                {"ip_cidr6": ["2606:4700::/32"]},
            ],
        ),
        (
            "metacubex_list",
            "metacubex-list",
            """
# comment
+.openai.com
.chatgpt.com
openaiapi-site.azureedge.net // inline comment
173.245.48.0/20
2400:cb00::/32
""",
            [
                {"domain": ["openaiapi-site.azureedge.net"]},
                {"domain_suffix": ["openai.com", "chatgpt.com"]},
                {"ip_cidr": ["173.245.48.0/20"]},
                {"ip_cidr6": ["2400:cb00::/32"]},
            ],
        ),
    ],
)
def test_parse_remote_formats(name, fmt, content, expected):
    assert parse_remote_content(content, fmt=fmt) == expected


def test_parse_v2fly_with_includes_tags_and_cycle_guard():
    files = {
        "https://example.com/data/category-ai": """
# header comment
include:openai
include:self-loop
midjourney.com # inline comment
""",
        "https://example.com/data/openai": """
include:category-ai
openai.com
domain:chatgpt.com
full:openaiapi-site.azureedge.net
keyword:oaistatic
regexp:^sora-.*\\.com$
full:tracker.example.com @ads @telemetry
""",
    }

    result = load_remote_rules(
        [
            {
                "url": "https://example.com/data/category-ai",
                "format": "v2fly",
                "exclude_tags": ["ads"],
            }
        ],
        fetcher=lambda u: files[u] if u in files else "",
    )

    assert result == [
        {"domain": ["openaiapi-site.azureedge.net"]},
        {"domain_suffix": ["openai.com", "chatgpt.com", "midjourney.com"]},
        {"domain_keyword": ["oaistatic"]},
        {"domain_regex": ["^sora-.*\\.com$"]},
    ]


def test_parse_v2fly_include_tags_filter():
    content = """
a.example.com @cn
b.example.com @!cn
c.example.com
"""
    result = parse_remote_content(content, fmt="v2fly", include_tags=["!cn"])
    assert result == [{"domain_suffix": ["b.example.com"]}]


def test_load_remote_rules_exclude_values_and_types():
    payload = json.dumps(
        {
            "version": 2,
            "rules": [
                {
                    "domain": ["drop.example.com", "keep.example.com"],
                    "domain_suffix": ["openai.com", "unwanted.ai"],
                    "domain_regex": "^drop$",
                }
            ],
        }
    )
    result = load_remote_rules(
        [
            {
                "url": "https://example.com/ai.json",
                "exclude": ["drop.example.com", "unwanted.ai"],
                "exclude_types": ["domain_regex"],
            }
        ],
        fetcher=lambda _: payload,
    )
    assert result == [
        {"domain": ["keep.example.com"]},
        {"domain_suffix": ["openai.com"]},
    ]


def test_load_remote_rules_propagates_fetch_error():
    def failing_fetcher(url: str) -> str:
        raise RuntimeError(f"network error for {url}")

    with pytest.raises(RuntimeError, match="network error"):
        load_remote_rules([{"url": "https://example.com/ai.json"}], fetcher=failing_fetcher)
