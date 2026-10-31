#!/usr/bin/env python3
"""Optional local-only evidence check. Never downloads or redistributes samples."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import themebridge as t
if len(sys.argv) != 3:
    raise SystemExit('Usage: python tests/verify_external.py ORIGINAL.xlsx REPORTER_FIXED.xlsx')
original, fixed = map(Path, sys.argv[1:])
raw = original.read_bytes(); other = fixed.read_bytes()
z, infos, before = t.inspect_archive(raw)
_, _, reference = t.inspect_archive(other)
after, changed = t.prefix_theme(before[t.THEME])
result = t.repack(raw,z,infos,after)
_, _, output = t.inspect_archive(result)
assert set(before) == set(reference)
assert [n for n in before if before[n] != reference[n]] == [t.THEME]
assert after == reference[t.THEME]
assert t.semantic(t.xml(before[t.THEME])) == t.semantic(t.xml(after))
assert all(before[n] == output[n] for n in before if n != t.THEME)
print(json.dumps({'original_sha256':t.sha(raw),'reporter_fixed_sha256':t.sha(other),'generated_sha256':t.sha(result),'generated_theme_matches_reporter_bytes':True,'unchanged_member_count':len(infos)-1,'semantic_equivalence':True,'application_test':'not run'},indent=2))
