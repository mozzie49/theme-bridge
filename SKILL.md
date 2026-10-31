---
name: themebridge
description: Offline narrow XLSX DrawingML default-namespace to explicit-prefix repair, with raw ZIP preservation and hash/equivalence report.
---

Use only for the default-namespace DrawingML theme interoperability case, not generic spreadsheet corruption or editing. Never open/render unknown workbooks or run macros. Do not use a spreadsheet library to reserialize the package.

1. Preserve the input. Run `python themebridge.py INPUT.xlsx --check` from this directory.
2. Read the JSON. If refused, report the exact reason. Do not weaken security/profile limits or silently use another editor. If already_prefixed, no repair is needed.
3. When a repaired copy is authorized, choose a new explicit output path and run `python themebridge.py INPUT.xlsx --output NEW.xlsx`. Never overwrite existing files. Capture stdout to a new report path only.
4. Require `xml_semantically_equivalent: true`, exactly `xl/theme/theme1.xml` changed, and unchanged hashes for every other member. Report original/result hashes and paths.
5. State the validation boundary: structural package repair only; no app rendering, recalculation, or formula execution. If authorized and a trusted application environment is available, test a disposable copy separately. Do not claim compatibility until that test succeeds.

The CLI rejects unsupported inputs rather than generalizing namespace rewrites. Read README.md for limits. Use `python -m unittest discover -s tests -v` after source changes.
