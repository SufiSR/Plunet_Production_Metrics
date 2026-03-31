from __future__ import annotations

from app.services.gitlab_release_collector import (
    _is_customer_release,
    _markers_regex,
    parse_tag_version,
)


def test_parse_tag_version_semver_with_prerelease() -> None:
    parsed = parse_tag_version("v10.2.3-rc.1")
    assert parsed.major == 10
    assert parsed.minor == 2
    assert parsed.patch == 3
    assert parsed.pre_release == "rc.1"


def test_parse_tag_version_non_semver_returns_none_fields() -> None:
    parsed = parse_tag_version("release-2026-03")
    assert parsed.major is None
    assert parsed.minor is None
    assert parsed.patch is None
    assert parsed.pre_release is None


def test_customer_release_false_for_configured_markers() -> None:
    marker_re = _markers_regex(["rc", "beta"])
    assert _is_customer_release("v10.1.0-rc.1", marker_re) is False
    assert _is_customer_release("v10.1.0-beta", marker_re) is False


def test_customer_release_true_for_final_version() -> None:
    marker_re = _markers_regex(["rc", "beta"])
    assert _is_customer_release("v10.1.0", marker_re) is True
