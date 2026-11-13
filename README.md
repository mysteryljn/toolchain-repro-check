# toolchain-repro-check

**Compare two toolchain lock manifests and gate reproducible builds.**

This Python 3.10+ CLI compares a small JSON inventory of compiler, linker,
SDK, and auxiliary tool versions. It reports additions, removals, version/path/
target changes, and optional SHA-256 digest changes as JSON, standalone HTML,
JUnit XML, or SARIF. It never runs a compiler and never assumes that a version
string alone proves bit-for-bit reproducibility.

## Try it in 60 seconds

```sh
git clone https://github.com/mysteryljn/toolchain-repro-check.git
cd toolchain-repro-check
python -m pip install .
python -m toolchain_repro_check demo --output report.html
```

The synthetic candidate changes a compiler version and digest, so the demo
report is intentionally a policy failure (exit status `1`). Compare your own
manifests in CI:

```sh
toolchain-repro-check compare baseline.json candidate.json \
  --fail-on tool-change --output toolchain.sarif
toolchain-repro-check validate baseline.json
```

Exit status is `0` when the selected policy passes, `1` when it finds a
violation, and `2` for invalid input or report I/O errors. A failed policy
still writes the report.

## Manifest format

```json
{
  "schema_version": 1,
  "toolchain": "arm-gcc",
  "generated_at": "2026-11-13T00:00:00Z",
  "tools": [
    {"name": "gcc", "version": "13.2.0", "path": "/opt/gcc/bin/gcc", "sha256": "<64 hex chars>", "target": "arm-none-eabi"}
  ]
}
```

`--fail-on tool-change` fails for removed tools and version, path, digest, or
target changes. `any-change` also fails for newly added tools; `none` only
produces a report. Use a separately generated manifest for each build image or
SDK archive and keep it under review with the build configuration.

## Limits

- The tool validates and compares declarations; it does not execute commands,
  inspect binaries, resolve packages, or prove deterministic compiler output.
- It does not understand vendor-specific version syntax; versions are compared
  as exact strings.
- A digest is evidence for the file selected by the producer, not a complete
  dependency closure. Record the manifest-generation process in your build.
- JSON is intentionally small and schema version 1; YAML, SPDX, and lockfile
  imports are outside this MVP.

## Development

```sh
python -m unittest discover -s tests -v
python -m pip wheel . --no-deps --wheel-dir dist
```

MIT licensed. Contributions should include a sanitized manifest fixture and a
regression test for every new policy rule.
