import pytest

from rule_merger import merge_rules, normalize_rule_blocks


@pytest.mark.parametrize(
    ("name", "raw_rules", "expected"),
    [
        ("empty", None, []),
        (
            "single_string_and_duplicates",
            [
                {"domain_suffix": ["openai.com", "chatgpt.com", "openai.com"]},
                {"domain_regex": "^foo.*$"},
                {"domain_suffix": ["chatgpt.com", "claude.ai"]},
            ],
            [
                {"domain_suffix": ["openai.com", "chatgpt.com", "claude.ai"]},
                {"domain_regex": ["^foo.*$"]},
            ],
        ),
        (
            "ordered_types_and_extra_key",
            [
                {"ip_cidr6": ["2400:cb00::/32"]},
                {"custom_key": ["val1"]},
                {"domain": ["api.openai.com"]},
                {"domain_suffix": ["openai.com"]},
            ],
            [
                {"domain": ["api.openai.com"]},
                {"domain_suffix": ["openai.com"]},
                {"ip_cidr6": ["2400:cb00::/32"]},
                {"custom_key": ["val1"]},
            ],
        ),
    ],
)
def test_normalize_rule_blocks(name, raw_rules, expected):
    assert normalize_rule_blocks(raw_rules) == expected


@pytest.mark.parametrize(
    ("name", "remote", "local", "expected"),
    [
        (
            "dedup_across_remote_and_local",
            [
                {"domain": ["openaiapi-site.azureedge.net"]},
                {"domain_suffix": ["openai.com", "sora.com"]},
            ],
            [
                {"domain_suffix": ["openai.com", "chatgpt.com"]},
            ],
            [
                {"domain": ["openaiapi-site.azureedge.net"]},
                {"domain_suffix": ["openai.com", "sora.com", "chatgpt.com"]},
            ],
        ),
        (
            "empty_remote",
            [],
            [{"domain_suffix": ["woa.com"]}],
            [{"domain_suffix": ["woa.com"]}],
        ),
    ],
)
def test_merge_rules(name, remote, local, expected):
    assert merge_rules(remote, local) == expected


def test_normalize_rule_blocks_invalid_entry():
    with pytest.raises(ValueError, match="字典类型"):
        normalize_rule_blocks(["not-a-dict"])  # type: ignore[list-item]
