"""Command line interface for toolchain-repro-check."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .core import ManifestError, VERSION, compare_manifests, load_manifest, parse_manifest, policy_findings, write_report


def _format_for(output: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    suffix = Path(output).suffix.lower()
    return {".html": "html", ".htm": "html", ".xml": "junit", ".sarif": "sarif", ".json": "json"}.get(suffix, "json")


def _options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", default="report.json")
    parser.add_argument("--format", choices=("json", "html", "junit", "sarif"))
    parser.add_argument("--fail-on", choices=("tool-change", "any-change", "none"), default="tool-change")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare toolchain lock manifests for reproducible builds")
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    compare = commands.add_parser("compare", help="compare two JSON manifests")
    compare.add_argument("before")
    compare.add_argument("after")
    _options(compare)
    demo = commands.add_parser("demo", help="compare packaged synthetic manifests")
    _options(demo)
    validate = commands.add_parser("validate", help="validate one manifest")
    validate.add_argument("manifest")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "demo":
            root = Path(__file__).parent / "fixtures"
            before = load_manifest(root / "baseline.json")
            after = load_manifest(root / "candidate.json")
            report = compare_manifests(before, after)
        elif args.command == "validate":
            manifest = load_manifest(args.manifest)
            print(f"valid manifest: {manifest.toolchain} ({len(manifest.tools)} tools)")
            return 0
        else:
            report = compare_manifests(load_manifest(args.before), load_manifest(args.after))
        report["policy"] = {"fail_on": args.fail_on, "violations": policy_findings(report, args.fail_on)}
        fmt = _format_for(args.output, args.format)
        write_report(report, args.output, fmt)
        return 1 if report["policy"]["violations"] else 0
    except (ManifestError, OSError, UnicodeError) as exc:
        print(f"toolchain-repro-check: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
