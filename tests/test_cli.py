from pathlib import Path
import tempfile
import unittest

from toolchain_repro_check.cli import main


BASE = {
    "schema_version": 1,
    "toolchain": "demo",
    "tools": [{"name": "gcc", "version": "13.2.0"}],
}


class CliTests(unittest.TestCase):
    def test_validate_accepts_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text('{"schema_version":1,"toolchain":"x","tools":[{"name":"cc","version":"1"}]}', encoding="utf-8")
            self.assertEqual(main(["validate", str(path)]), 0)

    def test_compare_writes_json_and_fails_on_version_change(self):
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / "before.json"
            after = Path(directory) / "after.json"
            output = Path(directory) / "report.json"
            before.write_text(__import__("json").dumps(BASE), encoding="utf-8")
            changed = {**BASE, "tools": [{"name": "gcc", "version": "14.0.0"}]}
            after.write_text(__import__("json").dumps(changed), encoding="utf-8")
            self.assertEqual(main(["compare", str(before), str(after), "--output", str(output)]), 1)
            self.assertIn("tool_version_changed", output.read_text(encoding="utf-8"))

    def test_compare_can_write_junit_without_failing_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / "before.json"
            after = Path(directory) / "after.json"
            output = Path(directory) / "report.xml"
            before.write_text(__import__("json").dumps(BASE), encoding="utf-8")
            after.write_text(__import__("json").dumps(BASE), encoding="utf-8")
            self.assertEqual(main(["compare", str(before), str(after), "--format", "junit", "--output", str(output)]), 0)
            self.assertIn("testsuite", output.read_text(encoding="utf-8"))

    def test_demo_writes_html_and_reports_policy_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "demo.html"
            self.assertEqual(main(["demo", "--output", str(output)]), 1)
            self.assertIn("Toolchain reproducibility report", output.read_text(encoding="utf-8"))

    def test_bad_json_returns_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            output = Path(directory) / "report.json"
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(main(["validate", str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
