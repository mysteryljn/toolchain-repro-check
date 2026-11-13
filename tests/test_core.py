import json
import tempfile
import unittest

from toolchain_repro_check.core import (
    ManifestError,
    compare_manifests,
    parse_manifest,
    policy_findings,
    render_report,
)


def manifest(tools):
    return parse_manifest({"schema_version": 1, "toolchain": "demo", "tools": tools})


class CoreTests(unittest.TestCase):
    def test_valid_manifest_round_trips(self):
        value = manifest([{"name": "gcc", "version": "13.2", "target": "arm"}])
        self.assertEqual(value.as_dict()["tools"][0]["version"], "13.2")

    def test_missing_toolchain_is_rejected(self):
        with self.assertRaises(ManifestError):
            parse_manifest({"tools": [{"name": "gcc", "version": "1"}]})

    def test_empty_tools_is_rejected(self):
        with self.assertRaises(ManifestError):
            parse_manifest({"toolchain": "x", "tools": []})

    def test_duplicate_names_are_rejected(self):
        with self.assertRaises(ManifestError):
            manifest([{"name": "gcc", "version": "1"}, {"name": "gcc", "version": "2"}])

    def test_bad_digest_is_rejected(self):
        with self.assertRaises(ManifestError):
            manifest([{"name": "gcc", "version": "1", "sha256": "1234"}])

    def test_digest_is_normalized_to_lowercase(self):
        digest = "A" * 64
        value = manifest([{"name": "gcc", "version": "1", "sha256": digest}])
        self.assertEqual(value.tools[0].sha256, "a" * 64)

    def test_version_change_is_error(self):
        old = manifest([{"name": "gcc", "version": "1"}])
        new = manifest([{"name": "gcc", "version": "2"}])
        report = compare_manifests(old, new)
        self.assertEqual(report["findings"][0]["rule_id"], "tool_version_changed")
        self.assertEqual(report["findings"][0]["level"], "error")

    def test_path_hash_and_target_changes_are_distinct(self):
        digest1 = "1" * 64
        digest2 = "2" * 64
        old = manifest([{"name": "gcc", "version": "1", "path": "/a", "sha256": digest1, "target": "x"}])
        new = manifest([{"name": "gcc", "version": "1", "path": "/b", "sha256": digest2, "target": "y"}])
        ids = {finding["rule_id"] for finding in compare_manifests(old, new)["findings"]}
        self.assertEqual(ids, {"tool_path_changed", "tool_hash_changed", "tool_target_changed"})

    def test_added_and_removed_tools_are_reported(self):
        old = manifest([{"name": "gcc", "version": "1"}, {"name": "ld", "version": "1"}])
        new = manifest([{"name": "gcc", "version": "1"}, {"name": "clang", "version": "1"}])
        ids = {finding["rule_id"] for finding in compare_manifests(old, new)["findings"]}
        self.assertEqual(ids, {"tool_added", "tool_removed"})

    def test_tool_change_policy_ignores_added_tools(self):
        old = manifest([{"name": "gcc", "version": "1"}])
        new = manifest([{"name": "gcc", "version": "1"}, {"name": "objcopy", "version": "1"}])
        report = compare_manifests(old, new)
        self.assertEqual(policy_findings(report, "tool-change"), [])
        self.assertEqual(len(policy_findings(report, "any-change")), 1)

    def test_none_policy_never_fails(self):
        old = manifest([{"name": "gcc", "version": "1"}])
        new = manifest([{"name": "gcc", "version": "2"}])
        self.assertEqual(policy_findings(compare_manifests(old, new), "none"), [])

    def test_all_report_formats_render(self):
        report = {"findings": [], "summary": {"finding_count": 0}}
        self.assertIn('"finding_count": 0', render_report(report, "json"))
        self.assertIn("<html", render_report(report, "html"))
        self.assertIn("testsuite", render_report(report, "junit"))
        self.assertIn('"version": "2.1.0"', render_report(report, "sarif"))


if __name__ == "__main__":
    unittest.main()
