#!/usr/bin/env python3
"""Create an original, synthetic XLSX ZIP fixture. No third-party workbook data."""
from pathlib import Path
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from themebridge import NS, REL, prefix_theme
S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
P = 'http://schemas.openxmlformats.org/package/2006/relationships'
colors = zip('dk1 lt1 dk2 lt2 accent1 accent2 accent3 accent4 accent5 accent6 hlink folHlink'.split(), ['101010','FFFFFF','303030','EEEEEE','336699','AA5533','668844','8855AA','339999','CC9933','0000FF','800080'])
clr = ''.join(f'<{n}><srgbClr val="{v}"/></{n}>' for n,v in colors)
font = '<latin typeface="Arial"/><ea typeface=""/><cs typeface=""/>'
fill = '<solidFill><schemeClr val="phClr"/></solidFill>'
line = '<ln w="9525" cap="flat" cmpd="sng" algn="ctr">'+fill+'<prstDash val="solid"/><miter lim="800000"/></ln>'
theme = ('<?xml version="1.0" encoding="UTF-8"?>\n<theme xmlns="'+NS+'" xmlns:a="'+NS+'" name="ThemeBridge Synthetic"><themeElements><clrScheme name="Synthetic">'+clr+'</clrScheme><fontScheme name="Synthetic"><majorFont>'+font+'</majorFont><minorFont>'+font+'</minorFont></fontScheme><fmtScheme name="Synthetic"><fillStyleLst>'+fill*3+'</fillStyleLst><lnStyleLst>'+line*3+'</lnStyleLst><effectStyleLst>'+'<effectStyle><effectLst/></effectStyle>'*3+'</effectStyleLst><bgFillStyleLst>'+fill*3+'</bgFillStyleLst></fmtScheme></themeElements></theme>').encode()
parts = {
'docProps/app.xml': '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>ThemeBridge synthetic fixture</Application></Properties>',
'docProps/core.xml': '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"/>',
'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="{P}"><Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{REL}/theme" Target="theme/theme1.xml"/><Relationship Id="rId3" Type="{REL}/styles" Target="styles.xml"/><Relationship Id="rId4" Type="{REL}/sharedStrings" Target="sharedStrings.xml"/></Relationships>',
'xl/styles.xml': f'<styleSheet xmlns="{S}"><fonts count="1"><font><sz val="11"/><color theme="1"/><name val="Arial"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
'xl/workbook.xml': f'<workbook xmlns="{S}" xmlns:r="{REL}"><sheets><sheet name="Synthetic" sheetId="1" r:id="rId1"/></sheets></workbook>',
'_rels/.rels': f'<Relationships xmlns="{P}"><Relationship Id="rId1" Type="{REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
'xl/worksheets/sheet1.xml': f'<worksheet xmlns="{S}"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1"><f>1+2</f><v>3</v></c></row></sheetData></worksheet>',
'xl/sharedStrings.xml': f'<sst xmlns="{S}" count="1" uniqueCount="1"><si><t>Independent synthetic example</t></si></sst>',
'xl/theme/theme1.xml': theme,
}
ctype = {'xl/workbook.xml':'spreadsheetml.sheet.main', 'xl/styles.xml':'spreadsheetml.styles','xl/worksheets/sheet1.xml':'spreadsheetml.worksheet','xl/sharedStrings.xml':'spreadsheetml.sharedStrings','xl/theme/theme1.xml':'theme','docProps/app.xml':'extended-properties','docProps/core.xml':'package.core-properties'}
parts['[Content_Types].xml'] = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'+''.join(f'<Override PartName="/{p}" ContentType="application/vnd.openxmlformats-officedocument.{t}+xml"/>' if p!='docProps/core.xml' else f'<Override PartName="/{p}" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>' for p,t in ctype.items())+'</Types>'
if __name__ == '__main__':
    output = Path(sys.argv[1]) if len(sys.argv)>1 else Path('synthetic.xlsx')
    with output.open('xb') as file, zipfile.ZipFile(file,'w',zipfile.ZIP_DEFLATED) as z:
        for n,d in parts.items():
            i=zipfile.ZipInfo(n,(2026,10,29,0,0,0));i.compress_type=8;z.writestr(i,d)
    print(output)
