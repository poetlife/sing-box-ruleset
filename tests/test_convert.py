import json
import subprocess

import pytest
import yaml

from convert import ClassicalClashRuleSet, SingBoxRuleSet, compile_all, compile_ruleset_file


def test_compile_ruleset_file_merges_remote_and_local(tmp_path, monkeypatch):
    monkeypatch.setattr("convert.shutil.which", lambda _: None)

    rulesets_dir = tmp_path / "rulesets"
    sources_dir = tmp_path / "sources"
    output_dir = tmp_path / "output"
    rulesets_dir.mkdir()
    sources_dir.mkdir()
    output_dir.mkdir()

    ruleset_yml = rulesets_dir / "proxy-only.yml"
    ruleset_yml.write_text(
        """
sing-box: true
clash: true
version: 1
remote_rules:
  - url: https://example.com/ai.json
    format: sing-box
rules:
  - domain_suffix:
      - openai.com
      - google.com
""",
        encoding="utf-8",
    )

    remote_json = json.dumps(
        {
            "version": 2,
            "rules": [
                {
                    "domain": ["openaiapi-site.azureedge.net"],
                    "domain_suffix": ["openai.com", "claude.ai"],
                    "domain_keyword": ["anthropic"],
                    "domain_regex": "^sora-.*$",
                }
            ],
        }
    )

    summary = compile_ruleset_file(
        str(ruleset_yml),
        sources_dir=str(sources_dir),
        output_dir=str(output_dir),
        fetcher=lambda _: remote_json,
    )

    assert summary["summary"] == {
        "domain": 1,
        "domain_suffix": 3,
        "domain_keyword": 1,
        "domain_regex": 1,
    }

    sb_data = json.loads((sources_dir / "proxy-only.json").read_text(encoding="utf-8"))
    assert sb_data == {
        "version": 1,
        "rules": [
            {"domain": ["openaiapi-site.azureedge.net"]},
            {"domain_suffix": ["openai.com", "claude.ai", "google.com"]},
            {"domain_keyword": ["anthropic"]},
            {"domain_regex": ["^sora-.*$"]},
        ],
    }

    clash_data = yaml.safe_load((output_dir / "clash-proxy-only.yaml").read_text(encoding="utf-8"))
    assert clash_data == {
        "payload": [
            "DOMAIN,openaiapi-site.azureedge.net",
            "DOMAIN-SUFFIX,openai.com",
            "DOMAIN-SUFFIX,claude.ai",
            "DOMAIN-SUFFIX,google.com",
            "DOMAIN-KEYWORD,anthropic",
            "DOMAIN-REGEX,^sora-.*$",
        ]
    }


def test_compile_all_backward_compatible_without_remote_rules(tmp_path, monkeypatch):
    monkeypatch.setattr("convert.shutil.which", lambda _: None)

    rulesets_dir = tmp_path / "rulesets"
    sources_dir = tmp_path / "sources"
    output_dir = tmp_path / "output"
    rulesets_dir.mkdir()

    (rulesets_dir / "cloudflare.yml").write_text(
        """
sing-box: false
clash: true
rules:
  - ip_cidr:
      - 173.245.48.0/20
  - ip_cidr6:
      - 2400:cb00::/32
""",
        encoding="utf-8",
    )

    results = compile_all(
        rulesets_dir=str(rulesets_dir),
        sources_dir=str(sources_dir),
        output_dir=str(output_dir),
    )

    assert len(results) == 1
    assert not (sources_dir / "cloudflare.json").exists()
    clash_data = yaml.safe_load((output_dir / "clash-cloudflare.yaml").read_text(encoding="utf-8"))
    assert clash_data == {
        "payload": [
            "IP-CIDR,173.245.48.0/20",
            "IP-CIDR6,2400:cb00::/32",
        ]
    }


def test_singbox_binary_compile_failure_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("convert.shutil.which", lambda _: "/usr/bin/sing-box")

    def fake_run(cmd, capture_output, text, check):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="invalid regex")

    monkeypatch.setattr("convert.subprocess.run", fake_run)

    sb = SingBoxRuleSet()
    sb.parse_rules([{"domain_suffix": ["openai.com"]}])

    with pytest.raises(RuntimeError, match="sing-box 编译失败"):
        sb.to_binary(str(tmp_path / "in.json"), str(tmp_path / "out.srs"))


def test_ruleset_class_supported_keys():
    sb = SingBoxRuleSet()
    sb.parse_rules(
        [
            {"domain": ["a.com"]},
            {"domain_suffix": ["b.com"]},
            {"domain_keyword": ["kw"]},
            {"domain_regex": ["^re$"]},
            {"ip_cidr": ["1.1.1.0/24"]},
        ]
    )
    assert sb.to_dict()["rules"] == [
        {"domain": ["a.com"]},
        {"domain_suffix": ["b.com"]},
        {"domain_keyword": ["kw"]},
        {"domain_regex": ["^re$"]},
    ]

    clash = ClassicalClashRuleSet()
    clash.parse_rules(
        [
            {"domain": ["a.com"]},
            {"domain_suffix": ["b.com"]},
            {"domain_keyword": ["kw"]},
            {"domain_regex": ["^re$"]},
            {"ip_cidr": ["1.1.1.0/24"]},
            {"ip_cidr6": ["2400:cb00::/32"]},
        ]
    )
    assert clash.to_dict()["payload"] == [
        "DOMAIN,a.com",
        "DOMAIN-SUFFIX,b.com",
        "DOMAIN-KEYWORD,kw",
        "DOMAIN-REGEX,^re$",
        "IP-CIDR,1.1.1.0/24",
        "IP-CIDR6,2400:cb00::/32",
    ]
