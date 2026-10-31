import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import themebridge as tb

THEME = ('<?xml version="1.0" encoding="UTF-8"?>\n'
         '<theme xmlns="'+tb.NS+'" xmlns:a="'+tb.NS+'" name="Synthetic Theme">'
         '<themeElements><clrScheme name="Synthetic"><dk1><srgbClr val="101010"/></dk1>'
         '</clrScheme><fontScheme name="Synthetic"><majorFont><latin typeface="Example Sans"/>'
         '</majorFont><minorFont><latin typeface="Example Sans"/></minorFont></fontScheme>'
         '<fmtScheme name="Synthetic"><fillStyleLst><solidFill><schemeClr val="phClr"/>'
         '</solidFill></fillStyleLst></fmtScheme></themeElements></theme>').encode()
CT = b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>'
PARTS = {'[Content_Types].xml': CT, 'xl/workbook.xml': b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>', 'xl/worksheets/sheet1.xml': b'<worksheet><sheetData><row><c><f>1+2</f><v>3</v></c></row></sheetData></worksheet>', tb.THEME: THEME}

def fixture(parts=None, descriptor=False):
    class Stream(io.BytesIO):
        def seekable(self): return False
        def seek(self, *args): raise io.UnsupportedOperation()
    stream = Stream() if descriptor else io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        z.comment = b'Original synthetic fixture, MIT'
        for name, data in (parts or PARTS).items():
            i = zipfile.ZipInfo(name, (2026, 10, 29, 12, 30, 0)); i.compress_type = 8
            i.comment = b'preserve'; i.external_attr = 0o100644 << 16
            z.writestr(i, data)
    return stream.getvalue()

def records(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = sorted(z.infolist(), key=lambda i: i.header_offset)
        return {i.filename:raw[i.header_offset:infos[j+1].header_offset if j+1<len(infos) else z.start_dir] for j,i in enumerate(infos)}

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)/'input.xlsx'; self.output = Path(self.tmp.name)/'output.xlsx'
    def run_repair(self, raw=None):
        self.source.write_bytes(raw or fixture()); return tb.repair(self.source, self.output)
    def test_only_theme_changes_and_metadata(self):
        for descriptor in (False, True):
            with self.subTest(descriptor=descriptor):
                self.output.unlink(missing_ok=True)
                raw = fixture(descriptor=descriptor); report = self.run_repair(raw)
                after = self.output.read_bytes()
                self.assertEqual(report['changed_members'], [tb.THEME])
                self.assertEqual(self.source.read_bytes(), raw)
                a,b = records(raw), records(after)
                for n in a:
                    if n != tb.THEME: self.assertEqual(a[n],b[n])
                with zipfile.ZipFile(io.BytesIO(raw)) as x, zipfile.ZipFile(io.BytesIO(after)) as y:
                    self.assertEqual(x.comment, y.comment)
                    for i,j in zip(x.infolist(),y.infolist()):
                        for k in ('date_time','external_attr','internal_attr','comment','extra','flag_bits','create_system','compress_type'):
                            self.assertEqual(getattr(i,k),getattr(j,k))
    def test_no_overwrite(self):
        self.run_repair(); previous = self.output.read_bytes()
        with self.assertRaises(FileExistsError): tb.repair(self.source,self.output)
        self.assertEqual(self.output.read_bytes(),previous)
        with self.assertRaises(FileExistsError): tb.repair(self.source,self.source)
    def test_dry_run(self):
        self.source.write_bytes(fixture()); r=tb.repair(self.source)
        self.assertEqual(r['status'],'repairable'); self.assertFalse(self.output.exists())
    def test_idempotent(self):
        self.run_repair(); r=tb.repair(self.output)
        self.assertEqual(r['status'],'already_prefixed'); self.assertEqual(r['changed_members'],[])
    def test_add_prefix_binding(self):
        data=THEME.replace((' xmlns:a="'+tb.NS+'"').encode(),b'')
        out,changed=tb.prefix_theme(data); self.assertTrue(changed)
        self.assertIn(b'xmlns:a=',out); self.assertNotIn(b'xmlns="',out)
    def test_entities_and_attribute_bytes(self):
        data=THEME.replace(b'Synthetic Theme',b'A &amp; B')
        out,_=tb.prefix_theme(data); self.assertIn(b'A &amp; B',out)
    def test_reject_theme_variants(self):
        variants=[THEME.replace(b'<themeElements>',b'<themeElements xmlns="urn:evil">'),
                  THEME.replace(b'<themeElements>',b'<themeElements unknown="x">'),
                  THEME.replace(b'val="101010"',b'val="a:Thing"'),
                  THEME.replace(b'<themeElements>',b'<themeElements xmlns:a="'+tb.NS.encode()+b'">'),
                  THEME.replace(b'<themeElements>',b'<themeElements><!-- comment -->'),
                  b'<!DOCTYPE theme [<!ENTITY x "bad">]>'+THEME,
                  THEME[:-8], THEME.replace(b'<themeElements>',b'<themeElements><?unsafe x?>')]
        for data in variants:
            with self.subTest(data=data[:60]), self.assertRaises(tb.Refused): tb.prefix_theme(data)
    def test_reject_package_variants(self):
        for name in ['../evil','/absolute','xl\\evil','xl/vbaProject.bin','_xmlsignatures/sig.xml','xl/macrosheets/sheet1.xml','xl/%2e%2e/x']:
            with self.subTest(name=name):
                with self.assertRaises(tb.Refused): tb.inspect_archive(fixture(dict(PARTS,**{name:b'x'})))
        parts=dict(PARTS);parts['[Content_Types].xml']=CT.replace(b'sheet.main',b'sheet.macroEnabled.main')
        with self.assertRaises(tb.Refused): tb.inspect_archive(fixture(parts))
    def test_zip_bomb(self):
        with self.assertRaises(tb.Refused): tb.inspect_archive(fixture(dict(PARTS,**{'bomb':b'0'*1000000})))
    def test_duplicate(self):
        stream=io.BytesIO(fixture())
        with zipfile.ZipFile(stream,'a') as z: z.writestr('XL/WORKBOOK.XML',b'x')
        with self.assertRaises(tb.Refused):tb.inspect_archive(stream.getvalue())
    def test_encrypted_flag(self):
        data=bytearray(fixture()); pos=data.index(b'PK\x01\x02');struct.pack_into('<H',data,pos+8,1)
        with self.assertRaises(tb.Refused):tb.inspect_archive(bytes(data))
    def test_cli_reports_refusal(self):
        self.source.write_bytes(b'not zip')
        p=subprocess.run([sys.executable,str(Path(tb.__file__)),str(self.source),'--check'],capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertEqual(json.loads(p.stderr)['status'],'refused')

if __name__ == '__main__': unittest.main()
