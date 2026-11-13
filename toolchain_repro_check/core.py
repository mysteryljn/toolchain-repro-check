"""Validation and comparison of small, reviewable toolchain lock manifests."""

from __future__ import annotations

from dataclasses import dataclass
import html
import json
from pathlib import Path
import re
from typing import Any
import xml.etree.ElementTree as ET

VERSION = "0.1.0"
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class ManifestError(ValueError):
    """Raised when a manifest is invalid or cannot be compared safely."""


@dataclass(frozen=True)
class Tool:
    name: str
    version: str
    path: str | None = None
    sha256: str | None = None
    target: str | None = None
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict:
        result = {"name": self.name, "version": self.version}
        for key, value in (("path", self.path), ("sha256", self.sha256), ("target", self.target)):
            if value is not None:
                result[key] = value
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass(frozen=True)
class Manifest:
    toolchain: str
    tools: tuple[Tool, ...]
    schema_version: int = 1
    generated_at: str | None = None

    def as_dict(self) -> dict:
        result = {"schema_version": self.schema_version, "toolchain": self.toolchain, "tools": [tool.as_dict() for tool in self.tools]}
        if self.generated_at is not None:
            result["generated_at"] = self.generated_at
        return result


def _string(value: Any, field: str, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{field} must be a non-empty string")
    return value.strip()


def parse_manifest(document: Any, source: str = "manifest") -> Manifest:
    if not isinstance(document, dict):
        raise ManifestError(f"{source}: top-level value must be an object")
    schema = document.get("schema_version", 1)
    if schema != 1:
        raise ManifestError(f"{source}: unsupported schema_version {schema!r}")
    toolchain = _string(document.get("toolchain"), f"{source}.toolchain", required=True)
    generated_at = _string(document.get("generated_at"), f"{source}.generated_at")
    raw_tools = document.get("tools")
    if not isinstance(raw_tools, list) or not raw_tools:
        raise ManifestError(f"{source}.tools must be a non-empty array")
    tools: list[Tool] = []
    names: set[str] = set()
    for index, raw in enumerate(raw_tools):
        prefix = f"{source}.tools[{index}]"
        if not isinstance(raw, dict):
            raise ManifestError(f"{prefix} must be an object")
        name = _string(raw.get("name"), f"{prefix}.name", required=True)
        if name in names:
            raise ManifestError(f"{source}: duplicate tool name {name!r}")
        names.add(name)
        version = _string(raw.get("version"), f"{prefix}.version", required=True)
        path = _string(raw.get("path"), f"{prefix}.path")
        sha256 = _string(raw.get("sha256"), f"{prefix}.sha256")
        if sha256 is not None and not _SHA256.fullmatch(sha256):
            raise ManifestError(f"{prefix}.sha256 must be a 64-character hexadecimal digest")
        target = _string(raw.get("target"), f"{prefix}.target")
        metadata = raw.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise ManifestError(f"{prefix}.metadata must be an object")
        tools.append(Tool(name, version, path, sha256.lower() if sha256 else None, target, metadata))
    return Manifest(toolchain, tuple(tools), schema, generated_at)


def load_manifest(path: str | Path) -> Manifest:
    source = str(path)
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"{source}: cannot read JSON manifest: {exc}") from exc
    return parse_manifest(document, source)


def _finding(rule_id: str, level: str, message: str, name: str, before: Any = None, after: Any = None) -> dict:
    result = {"rule_id": rule_id, "level": level, "tool": name, "message": message}
    if before is not None:
        result["before"] = before
    if after is not None:
        result["after"] = after
    return result


def compare_manifests(before: Manifest, after: Manifest) -> dict:
    findings: list[dict] = []
    before_map = {tool.name: tool for tool in before.tools}
    after_map = {tool.name: tool for tool in after.tools}
    for name in sorted(before_map.keys() - after_map.keys()):
        findings.append(_finding("tool_removed", "error", f"tool {name} was removed", name, before_map[name].as_dict()))
    for name in sorted(after_map.keys() - before_map.keys()):
        findings.append(_finding("tool_added", "warning", f"tool {name} was added", name, after=after_map[name].as_dict()))
    for name in sorted(before_map.keys() & after_map.keys()):
        old, new = before_map[name], after_map[name]
        if old.version != new.version:
            findings.append(_finding("tool_version_changed", "error", f"tool {name} version changed", name, old.version, new.version))
        if old.path != new.path:
            findings.append(_finding("tool_path_changed", "warning", f"tool {name} path changed", name, old.path, new.path))
        if old.sha256 != new.sha256:
            findings.append(_finding("tool_hash_changed", "error", f"tool {name} digest changed", name, old.sha256, new.sha256))
        if old.target != new.target:
            findings.append(_finding("tool_target_changed", "error", f"tool {name} target changed", name, old.target, new.target))
    return {
        "tool": "toolchain-repro-check",
        "version": VERSION,
        "before": before.as_dict(),
        "after": after.as_dict(),
        "summary": {
            "before_tools": len(before.tools),
            "after_tools": len(after.tools),
            "finding_count": len(findings),
            "changed_tools": len({finding["tool"] for finding in findings}),
        },
        "findings": findings,
    }


def policy_findings(report: dict, mode: str) -> list[dict]:
    if mode == "none":
        return []
    if mode == "any-change":
        return list(report.get("findings", []))
    return [finding for finding in report.get("findings", []) if finding["rule_id"] in {
        "tool_removed", "tool_version_changed", "tool_path_changed", "tool_hash_changed", "tool_target_changed",
    }]


def render_report(report: dict, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(report, indent=2, sort_keys=True) + "\n"
    if fmt == "html":
        body = html.escape(json.dumps(report, indent=2, sort_keys=True))
        return "<!doctype html><html><head><meta charset='utf-8'><title>Toolchain reproducibility report</title><style>body{font:14px monospace;margin:2rem}pre{white-space:pre-wrap}</style></head><body><h1>Toolchain reproducibility report</h1><pre>" + body + "</pre></body></html>\n"
    if fmt == "junit":
        findings = report.get("findings", [])
        suite = ET.Element("testsuite", name="toolchain-repro-check", tests="1", failures=str(bool(findings)))
        case = ET.SubElement(suite, "testcase", name="manifest comparison")
        if findings:
            failure = ET.SubElement(case, "failure", message=findings[0]["message"])
            failure.text = json.dumps(findings, sort_keys=True)
        return ET.tostring(suite, encoding="unicode") + "\n"
    if fmt == "sarif":
        results = [{"ruleId": finding["rule_id"], "level": "error" if finding["level"] == "error" else "warning", "message": {"text": finding["message"]}} for finding in report.get("findings", [])]
        return json.dumps({
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [{"tool": {"driver": {"name": "toolchain-repro-check", "version": VERSION}}, "results": results}],
        }, indent=2) + "\n"
    raise ManifestError(f"unsupported report format {fmt!r}")


def write_report(report: dict, output: str | Path, fmt: str) -> None:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(render_report(report, fmt), encoding="utf-8", newline="\n")
    temporary.replace(destination)
