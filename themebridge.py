#!/usr/bin/env python3
"""Offline, narrow DrawingML prefix repair. Standard library only."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import zlib

NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
THEME = 'xl/theme/theme1.xml'
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_MEMBER = 16 * 1024 * 1024
TAGS = set('theme themeElements clrScheme dk1 lt1 dk2 lt2 accent1 accent2 accent3 accent4 accent5 accent6 hlink folHlink sysClr srgbClr scrgbClr hslClr prstClr schemeClr fontScheme majorFont minorFont latin ea cs font fmtScheme fillStyleLst solidFill gradFill gsLst gs lin path fillToRect tileRect lnStyleLst ln prstDash bevel round miter headEnd tailEnd effectStyleLst effectStyle effectLst outerShdw innerShdw glow softEdge reflection blur scene3d camera lightRig rot backdrop anchor norm up sp3d bevelT bevelB extrusionClr contourClr bgFillStyleLst objectDefaults extraClrSchemeLst tint shade comp inv gray alpha alphaOff alphaMod hue hueOff hueMod sat satOff satMod lum lumOff lumMod red redOff redMod green greenOff greenMod blue blueOff blueMod gamma invGamma noFill pattFill fgClr bgClr'.split())
ATTRS = set('name val lastClr typeface panose pitchFamily charset script ang scaled flip rotWithShape pos path l t r b w cap cmpd algn prst lim type len rad blurRad dist dir sx sy kx ky algn grow fadeDir stA stPos endA endPos endSize stSize radius rig lat lon rev zoom fov z extrusionH contourW prstMaterial h'.split())
TAG = re.compile(r'<(/?)([A-Za-z_][\w.-]*(?::[A-Za-z_][\w.-]*)?)(\s+(?:[^>\'"]|\'[^\']*\'|"[^"]*")*|\s*)(/?)>')
DECL = re.compile(r'\s+xmlns(?::([A-Za-z_][\w.-]*))?\s*=\s*([\'"])(.*?)\2')
class Refused(ValueError):
    """Input is outside the explicitly supported profile."""
def need(ok, reason):
    if not ok:
        raise Refused(reason)
def sha(data):
    return hashlib.sha256(data).hexdigest()
def xml(data):
    need(len(data) <= MAX_MEMBER, 'XML size limit exceeded')
    try:
        s = data.decode('utf-8')
        need('<!' not in s, 'DOCTYPE, entities, comments and CDATA are unsupported')
        need(not re.search(r'<\?(?!xml\s)', s), 'Processing instructions unsupported')
        return ET.fromstring(data)
    except (UnicodeError, ET.ParseError) as e:
        raise Refused('Malformed or non-UTF-8 XML') from e

def semantic(node):
    return (node.tag, sorted(node.attrib.items()), node.text, node.tail,
            [semantic(c) for c in node])

def prefix_theme(data):
    root = xml(data)
    need(root.tag == '{'+NS+'}theme', 'Not a transitional DrawingML theme')
    need([c.tag for c in root].count('{'+NS+'}themeElements') == 1, 'Expected one themeElements')
    for n in root.iter():
        need(n.tag.startswith('{'+NS+'}') and n.tag.split('}', 1)[1] in TAGS,
             'Unsupported DrawingML element')
        for k, v in n.attrib.items():
            need(k in ATTRS and ':' not in v, 'Unsupported or QName-ambiguous attribute')
    s = data.decode('utf-8')
    tokens = list(TAG.finditer(s))
    need(bool(tokens), 'No theme tokens')
    first = tokens[0]
    declarations = [(p or '', v) for p, _, v in DECL.findall(first.group())]
    need(len(declarations) == len(set(p for p, _ in declarations)), 'Duplicate namespace')
    namespaces = dict(declarations)
    need(set(namespaces) <= {'', 'a', 'r'}, 'Unsupported namespace declarations')
    need(all(v == (REL if p == 'r' else NS) for p, v in declarations), 'Namespace mismatch')
    default = namespaces.get('') == NS
    need(default or namespaces.get('a') == NS, 'Expected default or a namespace')
    for m in tokens:
        need(m is first or not DECL.search(m.group()), 'Nested namespace declarations unsupported')
        name = m.group(2)
        need(name.startswith('a:') or ':' not in name and default, 'Unsupported lexical element prefix')
    if not default:
        return data, False
    def replace(m):
        text = m.group()
        if m.start() == first.start():
            text = DECL.sub(lambda d: '' if d.group(1) is None else d.group(), text)
            if 'a' not in namespaces:
                at = text.index('>') - (1 if text.endswith('/>') else 0)
                text = text[:at] + ' xmlns:a="'+NS+'"' + text[at:]
        if ':' not in m.group(2):
            offset = 2 if m.group(1) else 1
            text = text[:offset] + 'a:' + text[offset:]
        return text
    result = TAG.sub(replace, s).encode('utf-8')
    need(semantic(root) == semantic(xml(result)), 'XML semantic comparison failed')
    return result, True

def inspect_archive(raw):
    need(len(raw) <= MAX_ARCHIVE, 'Archive size limit exceeded')
    need(raw.startswith(b'PK\x03\x04'), 'Not a plain ZIP XLSX (encrypted/OLE unsupported)')
    z = zipfile.ZipFile(io.BytesIO(raw))
    infos = z.infolist()
    need(0 < len(infos) <= 2048, 'ZIP entry count limit exceeded')
    names = [i.filename for i in infos]
    need(len(set(n.casefold() for n in names)) == len(names), 'Duplicate ZIP entries')
    total = 0
    for i in infos:
        n = i.filename
        need(n == i.orig_filename and '\\' not in n and not n.startswith('/') and
             all(p not in ('', '.', '..') for p in n.split('/')) and ':' not in n and '%' not in n,
             'Unsafe ZIP entry name')
        need(i.flag_bits & ~0x808 == 0 and i.compress_type in (0, 8), 'Unsupported ZIP flags/compression')
        need(i.file_size <= MAX_MEMBER and i.file_size <= max(i.compress_size, 1)*200, 'ZIP expansion limit exceeded')
        total += i.file_size
        need(total <= MAX_TOTAL, 'ZIP total expansion limit exceeded')
        need(not any(x in n.lower() for x in ('vba', 'macrosheet', 'dialogsheets', '_xmlsignatures', 'signature', 'encrypted')), 'Macro/signed/encrypted package refused')
        need((i.external_attr >> 16) & 0o170000 != 0o120000, 'Symlink ZIP entry refused')
        # Do not permit ZIP64 extra fields.
        pos = 0
        while pos < len(i.extra):
            need(pos+4 <= len(i.extra), 'Malformed ZIP extra field')
            kind, size = struct.unpack_from('<HH', i.extra, pos)
            need(kind in (0x5455, 0x000a, 0x7875) and pos+4+size <= len(i.extra), 'Unsupported/malformed ZIP extra field')
            pos += 4+size
    need({'[Content_Types].xml', 'xl/workbook.xml', THEME} <= set(names), 'Missing XLSX package parts')
    decoded = {}
    ordered = sorted(infos, key=lambda i: i.header_offset)
    need(ordered[0].header_offset == 0, 'ZIP preamble unsupported')
    for index, i in enumerate(ordered):
        start = i.header_offset
        end = ordered[index+1].header_offset if index+1 < len(ordered) else z.start_dir
        need(0 <= start < end <= len(raw) and end-start >= 30, 'Invalid local record bounds')
        need(raw[start:start+4] == b'PK\x03\x04', 'Invalid local header')
        flags, method = struct.unpack_from('<HH', raw, start+6)
        crc, compressed, uncompressed = struct.unpack_from('<III', raw, start+14)
        fn, ex = struct.unpack_from('<HH', raw, start+26)
        need(flags == i.flag_bits and method == i.compress_type, 'Local/central ZIP flags or compression mismatch')
        data_start = start+30+fn+ex
        need(data_start+i.compress_size <= end, 'Truncated local record')
        encoding = 'utf-8' if flags & 0x800 else 'cp437'
        need(raw[start+30:start+30+fn] == i.filename.encode(encoding), 'Local/central filename mismatch')
        payload = raw[data_start:data_start+i.compress_size]
        if method == 8:
            decoder = zlib.decompressobj(-15)
            try:
                member = decoder.decompress(payload, i.file_size+1)
            except zlib.error as e:
                raise Refused('Invalid DEFLATE stream') from e
            need(len(member) == i.file_size and decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data,
                 'DEFLATE size mismatch, trailing data, or expansion limit exceeded')
        else:
            need(i.compress_size == i.file_size, 'Stored ZIP size mismatch')
            member = payload
        need(zlib.crc32(member) == i.CRC, 'ZIP member CRC mismatch')
        decoded[i.filename] = member
        extra = raw[start+30+fn:data_start]; pos = 0
        while pos < len(extra):
            need(pos+4 <= len(extra), 'Malformed local ZIP extra')
            kind, length = struct.unpack_from('<HH', extra, pos)
            need(kind in (0x5455, 0x000a, 0x7875) and pos+4+length <= len(extra), 'Unsupported/malformed local ZIP extra field')
            pos += 4+length
        expected = (i.CRC, i.compress_size, i.file_size)
        tail = raw[data_start+i.compress_size:end]
        if flags & 8:
            need((crc, compressed, uncompressed) in ((0, 0, 0), expected), 'Invalid descriptor local sizes')
            if tail.startswith(b'PK\x07\x08'):
                tail = tail[4:]
            need(len(tail) == 12 and struct.unpack('<III', tail) == expected, 'Invalid ZIP data descriptor')
        else:
            need((crc, compressed, uncompressed) == expected and not tail, 'Local/central size or CRC mismatch')
    contents = {}
    for i in infos:
        contents[i.filename] = decoded[i.filename]  # bounded decompression + exact length/CRC validated above
        if i.filename.endswith(('.xml', '.rels')):
            root = xml(contents[i.filename])
            if i.filename == '[Content_Types].xml':
                types = [n.attrib.get('ContentType', '').lower() for n in root]
                need(not any(any(t in c for t in ('macro', 'vba', 'signature', 'encrypted')) for c in types), 'Unsafe content type')
                need('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml' in types, 'Not an ordinary XLSX workbook')
            if i.filename.endswith('.rels'):
                need(not any(any(x in n.attrib.get('Type', '').lower() for x in ('vba', 'signature', 'macrosheet')) for n in root), 'Unsafe relationship type')
    return z, infos, contents

def repack(raw, z, infos, replacement):
    # Keep every untouched local record (including compressed bytes/descriptors) verbatim.
    cd = z.start_dir
    ordered = sorted(infos, key=lambda i: i.header_offset)
    need(ordered[0].header_offset == 0, 'ZIP preamble unsupported')
    out = bytearray(); offsets = {}
    for idx, i in enumerate(ordered):
        start = i.header_offset
        end = ordered[idx+1].header_offset if idx+1 < len(ordered) else cd
        need(start < end <= cd, 'Invalid ZIP record boundaries')
        offsets[i.filename] = len(out)
        chunk = raw[start:end]
        if i.filename == THEME:
            need(chunk[:4] == b'PK\x03\x04', 'Invalid local header')
            fn, extra = struct.unpack_from('<HH', chunk, 26)
            header = bytearray(chunk[:30+fn+extra])
            payload = replacement
            if i.compress_type == 8:
                compressor = zlib.compressobj(6, zlib.DEFLATED, -15)
                payload = compressor.compress(replacement) + compressor.flush()
            crc = zlib.crc32(replacement)
            if i.flag_bits & 8:
                struct.pack_into('<III', header, 14, 0, 0, 0)
                descriptor = struct.pack('<4sIII', b'PK\x07\x08', crc, len(payload), len(replacement))
            else:
                struct.pack_into('<III', header, 14, crc, len(payload), len(replacement))
                descriptor = b''
            chunk = header + payload + descriptor
            changed = (crc, len(payload), len(replacement))
        out.extend(chunk)
    new_cd = len(out); pos = cd
    for i in infos:
        need(raw[pos:pos+4] == b'PK\x01\x02', 'Invalid central directory')
        fn, ex, co = struct.unpack_from('<HHH', raw, pos+28)
        length = 46+fn+ex+co
        rec = bytearray(raw[pos:pos+length])
        struct.pack_into('<I', rec, 42, offsets[i.filename])
        if i.filename == THEME:
            struct.pack_into('<III', rec, 16, *changed)
        out.extend(rec); pos += length
    need(raw[pos:pos+4] == b'PK\x05\x06' and pos+22 <= len(raw), 'ZIP64 or extra central records unsupported')
    disk, cd_disk, disk_count, count, cd_size, cd_offset, comment = struct.unpack_from('<HHHHIIH', raw, pos+4)
    need(disk == cd_disk == 0 and disk_count == count == len(infos) and cd_offset == cd and cd_size == pos-cd and pos+22+comment == len(raw), 'Invalid/multipart ZIP footer')
    footer = bytearray(raw[pos:]); struct.pack_into('<I', footer, 16, new_cd); out.extend(footer)
    return bytes(out)

def repair(source, output=None):
    source = Path(source)
    need(source.stat().st_size <= MAX_ARCHIVE, 'Archive size limit exceeded')
    raw = source.read_bytes()
    z, infos, before = inspect_archive(raw)
    transformed, changed = prefix_theme(before[THEME])
    rebuilt = repack(raw, z, infos, transformed)  # validates footer even on no-op
    result = rebuilt if changed else raw
    _, after_infos, after = inspect_archive(result)
    need(all(after[n] == b for n, b in before.items() if n != THEME), 'Unrelated member changed')
    need(semantic(xml(before[THEME])) == semantic(xml(after[THEME])), 'Semantic equivalence failed')
    report = {'tool': 'ThemeBridge', 'version': '0.1.0', 'status': 'repairable' if changed else 'already_prefixed', 'source': str(source), 'output': str(output) if output else None, 'source_sha256': sha(raw), 'result_sha256': sha(result), 'changed_members': [THEME] if changed else [], 'xml_semantically_equivalent': True, 'untouched_member_count': len(infos)-(1 if changed else 0), 'application_compatibility': 'not tested; structural repair only', 'members': [{'name': n, 'before_sha256': sha(b), 'after_sha256': sha(after[n]), 'changed': b != after[n]} for n, b in before.items()]}
    if output is not None:
        # Exclusive create: never truncate an existing path, including aliases/symlinks.
        destination = Path(output)
        fd, temporary = tempfile.mkstemp(prefix='.themebridge-', dir=destination.parent)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(result)
                f.flush()
                os.fsync(f.fileno())
            # Same-directory hard link atomically publishes complete bytes, refusing
            # any existing file/symlink. No overwrite fallback on unsupported FS.
            os.link(temporary, destination)
        finally:
            os.unlink(temporary)
        report['status'] = 'written' if changed else 'copied_already_prefixed'
    return report

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', '--dry-run', action='store_true', dest='check', help='validate and report without writing')
    group.add_argument('--output', type=Path, help='new output path; existing paths refused')
    args = p.parse_args(argv)
    try:
        print(json.dumps(repair(args.source, args.output), indent=2, ensure_ascii=False))
        return 0
    except (Refused, OSError, zipfile.BadZipFile, RuntimeError, struct.error, RecursionError) as e:
        print(json.dumps({'status': 'refused', 'reason': str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
if __name__ == '__main__':
    sys.exit(main())
