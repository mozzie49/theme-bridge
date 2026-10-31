# Evidence and validation boundary

Checked 2026-10-31. Motivation: [ONLYOFFICE/DesktopEditors issue #2541](https://github.com/ONLYOFFICE/DesktopEditors/issues/2541), opened 2026-10-29. At inspection it was open, unassigned, with no linked development branch/PR. Reporter described ONLYOFFICE 10.0.0 rejecting a workbook and provided a manually prefixed counterpart. This is reporter evidence, not an application test performed by ThemeBridge.

Public reference attachments (not bundled; third-party license not established):

- [Original workbook](https://github.com/user-attachments/files/34145435/0-original.xlsx), 6,218 bytes, SHA-256 `b8fc15f5f89e29c124f7fc672414fae8bed72fb39fee067767ecc41ef87c0838`.
- [Reporter-prefixed workbook](https://github.com/user-attachments/files/34145432/11-original-only-theme-prefixed.xlsx), 5,962 bytes, SHA-256 `0465870848831aa0c37fe67bd14eb043d811c07af8a07f8f58fa66a36d42fba1`.

Private validation established:

1. Both packages contain the same 10 named members; exactly `xl/theme/theme1.xml` differs in uncompressed content.
2. Original and reporter-fixed theme trees have equal expanded element names, attributes, text, tails and child order.
3. ThemeBridge's generated theme XML is **byte-for-byte identical** to the reporter's manually changed theme XML.
4. ThemeBridge preserves the other nine raw local ZIP records; the synthetic descriptor/non-descriptor regression tests independently verify this invariant.
5. Generated full ZIP SHA-256: `1f32955a12b02bdef6b9c24a218b39d2d78c760540f39b4ab87d2372f3d7322c`. It differs from the reporter-fixed ZIP because ThemeBridge retains original package metadata/compression records rather than recreating the full archive.

The machine-readable evidence is in `external-validation.json`. To reproduce after independently acquiring the two references, run `python tests/verify_external.py ORIGINAL.xlsx REPORTER_FIXED.xlsx`. No download is automatic; samples are never executed. Do not commit or redistribute the reference files.

Independent review added hostile ZIP/XML and output-publication regressions. Final local test command: `python -m unittest discover -s tests -v` (24 tests passed). Syntax compilation also passed. CI configuration covers Python 3.10, 3.12 and 3.13, but no remote CI run is claimed.

This is not full OPC/XSD validation. `repairable` means the tool recognizes its supported lexical/namespace profile, not that the workbook is schema-valid or will open in any application. No ONLYOFFICE, Excel or Numbers rendering was performed. No fixes to those applications or upstream Excelize are claimed. Third-party workbooks are excluded; included code and synthetic examples are independently authored MIT material.
