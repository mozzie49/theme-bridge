"""Independent adversarial regressions; all package bytes are synthetic."""
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib
from test_themebridge import fixture, PARTS, THEME, records, tb

class SecurityReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'source.xlsx'
        self.output = Path(self.tmp.name) / 'output.xlsx'

    def reject(self, raw):
        self.source.write_bytes(raw)
        with self.assertRaises((tb.Refused, zipfile.BadZipFile)):
            tb.repair(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_local_central_mismatches(self):
        for offset, fmt, value in [(6, '<H', 1), (8, '<H', 99), (14, '<I', 123), (18, '<I', 1), (22, '<I', 1)]:
            with self.subTest(offset=offset):
                raw = bytearray(fixture()); struct.pack_into(fmt, raw, offset, value)
                self.reject(raw)

    def test_noop_multidisk_footer_and_trailing_data(self):
        parts = dict(PARTS); parts[tb.THEME] = tb.prefix_theme(THEME)[0]
        raw = bytearray(fixture(parts)); pos = raw.rfind(b'PK\x05\x06')
        struct.pack_into('<H', raw, pos + 4, 1)
        self.reject(raw)
        self.reject(fixture(parts) + b'unexpected')

    def test_underreported_deflate_expansion(self):
        raw = bytearray(fixture(dict(PARTS, **{'opaque.bin': b'X' * 1000000})))
        z = zipfile.ZipFile(io.BytesIO(raw)); item = z.getinfo('opaque.bin')
        struct.pack_into('<I', raw, item.header_offset + 14, zlib.crc32(b'X'))
        struct.pack_into('<I', raw, item.header_offset + 22, 1)
        pos = z.start_dir
        for item in z.infolist():
            fn, ex, co = struct.unpack_from('<HHH', raw, pos + 28)
            if item.filename == 'opaque.bin':
                struct.pack_into('<I', raw, pos + 16, zlib.crc32(b'X'))
                struct.pack_into('<I', raw, pos + 24, 1)
            pos += 46 + fn + ex + co
        self.reject(raw)

    def test_local_unicode_path_override(self):
        stream = io.BytesIO(fixture())
        with zipfile.ZipFile(stream, 'a') as archive:
            info = zipfile.ZipInfo('ordinary.bin')
            payload = b'\x01' + struct.pack('<I', zlib.crc32(b'ordinary.bin')) + b'../evil'
            info.extra = struct.pack('<HH', 0x7075, len(payload)) + payload
            archive.writestr(info, b'synthetic')
        raw = bytearray(stream.getvalue())
        archive = zipfile.ZipFile(io.BytesIO(raw)); pos = archive.start_dir
        for item in archive.infolist():
            fn, ex, co = struct.unpack_from('<HHH', raw, pos + 28)
            if item.orig_filename == 'ordinary.bin':
                struct.pack_into('<H', raw, pos + 46 + fn, 0xcafe)
            pos += 46 + fn + ex + co
        self.reject(raw)

    def test_corrupt_data_descriptor(self):
        raw = bytearray(fixture(descriptor=True))
        pos = raw.index(b'PK\x07\x08')
        raw[pos + 4] ^= 1
        self.reject(raw)

    def test_signed_encrypted_macro_types(self):
        for ct in ['application/vnd.ms-office.vbaProject', 'application/vnd.openxmlformats-package.digital-signature-xmlsignature+xml', 'application/encrypted']:
            parts = dict(PARTS)
            parts['[Content_Types].xml'] = parts['[Content_Types].xml'].replace(b'</Types>', ('<Override ContentType="'+ct+'"/></Types>').encode())
            with self.subTest(ct=ct): self.reject(fixture(parts))

    def test_doctype_external_entities(self):
        parts = dict(PARTS)
        parts['xl/workbook.xml'] = b'<!DOCTYPE workbook [<!ENTITY external SYSTEM "file:///etc/passwd">]><workbook>&external;</workbook>'
        self.reject(fixture(parts))

    def test_qname_and_extension_rejection(self):
        for data in [THEME.replace(b'name="Synthetic Theme"', b'name="a:SomeType"'), THEME.replace(b'<themeElements>', b'<themeElements><extLst/>'), THEME.replace(b'val="101010"', b'val="a&#58;SomeType"')]:
            parts = dict(PARTS); parts[tb.THEME] = data
            with self.subTest(data=data): self.reject(fixture(parts))

    def test_output_existing_dangling_symlink_and_hardlink(self):
        self.source.write_bytes(fixture())
        self.output.symlink_to(Path(self.tmp.name) / 'missing.xlsx')
        with self.assertRaises(FileExistsError): tb.repair(self.source, self.output)
        self.assertTrue(self.output.is_symlink())
        self.output.unlink(); self.output.hardlink_to(self.source)
        before = self.source.read_bytes()
        with self.assertRaises(FileExistsError): tb.repair(self.source, self.output)
        self.assertEqual(self.source.read_bytes(), before)

    def test_atomic_failure_before_publication(self):
        self.source.write_bytes(fixture())
        with patch.object(tb.os, 'fsync', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError): tb.repair(self.source, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(Path(self.tmp.name).glob('.themebridge-*')), [])

    def test_atomic_publication_failure_cleanup(self):
        self.source.write_bytes(fixture())
        with patch.object(tb.os, 'link', side_effect=OSError('synthetic unsupported filesystem')):
            with self.assertRaises(OSError): tb.repair(self.source, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(Path(self.tmp.name).glob('.themebridge-*')), [])

    def test_non_theme_raw_records_preserved(self):
        for descriptor in (False, True):
            self.output.unlink(missing_ok=True)
            raw = fixture(descriptor=descriptor); self.source.write_bytes(raw)
            tb.repair(self.source, self.output)
            before, after = records(raw), records(self.output.read_bytes())
            for name in before:
                if name != tb.THEME: self.assertEqual(before[name], after[name])

if __name__ == '__main__': unittest.main()
