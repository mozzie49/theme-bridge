# ThemeBridge

**Experimental, offline XLSX theme-prefix repair. Python 3.10+, standard library only.**

Some producers write a DrawingML theme using the default namespace. ThemeBridge makes those element names explicitly `a:`-prefixed, a narrow workaround motivated by [ONLYOFFICE DesktopEditors #2541](https://github.com/ONLYOFFICE/DesktopEditors/issues/2541). This is not a spreadsheet editor or a general XLSX repair tool.

```sh
python themebridge.py original.xlsx --check
python themebridge.py original.xlsx --output repaired.xlsx > report.json
# --dry-run is an alias of --check
```

The output path must not exist. Input is never overwritten. JSON stdout records input/output paths, SHA-256 hashes, changed members, and XML semantic equivalence. Exit codes: `0` validated/written; `2` refused or I/O error (JSON stderr); invalid command syntax also exits `2`. `repairable` means a supported lexical/namespace profile, not a schema-valid workbook or proven app compatibility. A refused file is not proof of corruption: it may simply be outside the narrow profile. Shell redirection of reports is controlled by your shell; choose a new report filename.

## What changes

Only `xl/theme/theme1.xml`: remove its root default DrawingML namespace declaration, introduce/reuse `xmlns:a`, prefix unprefixed element names. Existing attribute values, text, whitespace, lexical escaping, and other declarations remain unchanged. Before/after trees must match in expanded element names, attributes, text, tails, and child order.

All other members' **entire raw local ZIP records** are copied, including compressed bytes and descriptors. Central-directory metadata is retained except necessary local-header offsets; theme CRC/sizes are updated. Archive comment and member ordering are preserved. Theme compression bytes and descriptor encoding may change; the whole ZIP hash necessarily changes. File-system timestamps/permissions of the source are not copied. Output is atomically published using a same-directory temporary file and an exclusive hard link. Filesystems that cannot support this operation are refused, without an overwrite fallback.

No cells, formulas, styles, cached results, external links, or macros are executed, recalculated, rendered, or reserialized. Existing package data is not made trustworthy by this operation: do not open untrusted repaired workbooks merely because the tool accepted them.

## Strict admission profile

- Ordinary, unsigned, unencrypted transitional XLSX; exact theme path above. ZIP32, single disk, stored/deflate only; central/local headers and descriptors must agree.
- Root DrawingML default namespace and optional `a`/`r` bindings, or an already `a:`-prefixed theme. Nested namespace declarations, foreign elements, unknown theme tags/attributes and attribute values containing `:` are refused to avoid QName ambiguity. This intentionally rejects some legitimate themes.
- UTF-8 XML only. DOCTYPE, entity declarations, comments, CDATA and non-declaration processing instructions are refused in all XML/rels members. Built-in escapes such as `&amp;` are supported.
- Rejects macro/signature/encryption names, content types and relevant relationships, duplicates/case collisions, unsafe paths, symlink entries, ZIP64, unknown extra-field types (only NTFS/extended timestamps and Unix UID/GID fields are admitted), and inconsistent ZIP metadata. This is a conservative admission check, **not malware scanning or full OPC/XSD validation**.
- Limits: 32 MiB archive, 2,048 entries, 16 MiB/member, 64 MiB total expanded, 200:1 member expansion. Package bytes stay in memory; nothing is extracted to paths.

**Compatibility boundary:** structural equivalence is tested. ONLYOFFICE/DesktopEditors rendering has **not** been run here, so repaired colors/fonts or application success are not promised. Test a copy in the target application before adopting the workaround. Preserve the original.

## Reproduce

```sh
python -m unittest discover -s tests -v
python examples/make_fixture.py synthetic.xlsx
python themebridge.py synthetic.xlsx --output synthetic-fixed.xlsx > synthetic-report.json
```

`examples/before.xml` and `after.xml` are original synthetic examples. The generator creates a 10-member synthetic package containing a string and a cached `1+2` formula; no third-party sample data. Tests cover descriptor/non-descriptor ZIPs, exact untouched records, metadata, no overwrite, dry run, idempotence and hostile inputs. CI is supplied, not claimed to have run remotely. See [evidence](docs/EVIDENCE.md). Original code and synthetic fixtures: MIT.

## 中文说明

ThemeBridge 是离线、实验性的 XLSX 主题命名空间修复工具，仅依赖 Python 标准库。它把 `xl/theme/theme1.xml` 中使用默认 DrawingML 命名空间的元素转换为显式 `a:` 前缀，针对上方 ONLYOFFICE 问题提供一个可检查的结构性变通方案。

先运行 `--check`（或 `--dry-run`），再用 `--output 新文件.xlsx` 写入新文件。不会覆盖原文件或已有输出。JSON 报告列出源文件/结果 SHA-256、唯一修改的 ZIP 成员以及 XML 语义等价检查。其他成员的压缩数据和本地 ZIP 记录逐字节保留，不改写单元格、公式或样式，不运行宏、不重新计算。

工具严格拒绝宏、签名、加密包、危险路径、重复条目、ZIP 炸弹、DOCTYPE/实体声明及不支持的命名空间结构。部分合法工作簿也会被拒绝；这不表示文件损坏。它不是病毒扫描器，也不是完整的 OOXML 合规验证器。

**尚未在 ONLYOFFICE 中进行打开/渲染验证，不能保证显示问题已解决。** 请保留原件，仅在副本上验证。第三方原始附件仅用于私有验证，不随项目分发。项目包含独立编写的合成示例和可复现测试，采用 MIT 许可证。
