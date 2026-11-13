# toolchain-repro-check

比较两个 JSON 工具链清单，检查编译器、链接器和 SDK 的版本、路径、目标
架构及 SHA-256 摘要变化，并生成 JSON、独立 HTML、JUnit XML 或 SARIF 报告。

```sh
python -m pip install .
python -m toolchain_repro_check demo --output report.html
python -m toolchain_repro_check compare baseline.json candidate.json --fail-on tool-change --output report.sarif
```

工具只验证清单声明，不执行编译器，也不声称单凭版本字符串就能证明位级
可复现构建。支持 Python 3.10+，MIT 许可。
