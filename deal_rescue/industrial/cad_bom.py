"""Conservative drawing/BOM intake. NEVER infer unshown specifications from geometry.

Supported: CSV, JSON BOM, DXF ASCII BLOCK INSERT occurrences, SVG structured
BOM annotations, text-only PDF BOM lines when pypdf is installed.
STEP/STL geometry, scanned PDFs and unsupported DXF yield Z and require user BOM.
All formats are strictly bounded; no user files are retained or sent to suppliers.
"""
from __future__ import annotations
import csv
import io
import json
import re
import hashlib
from collections import Counter
from xml.etree import ElementTree as ET

MAX_BYTES = 2 * 1024 * 1024
MAX_PARTS = 300
ALLOW = {'.csv', '.json', '.dxf', '.svg', '.pdf', '.step', '.stp', '.stl'}
CODE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._+\-/]{0,79}$')
BOM_TEXT = re.compile(r'^\s*([A-Za-z0-9][A-Za-z0-9._+\-/]{0,79})\s*[,;|\t]\s*(\d{1,5})\s*$', re.M)

class IntakeError(ValueError): pass

def _rows(rows, origin):
    out = []
    for row in rows:
        name = str(row.get('part_no') or row.get('part') or row.get('sku') or '').strip()
        qty = row.get('qty', row.get('quantity', 0))
        if not CODE.fullmatch(name): raise IntakeError('INVALID_PART_NUMBER')
        if isinstance(qty, bool) or not str(qty).isdigit() or not 0 < int(qty) <= 100000:
            raise IntakeError('INVALID_QUANTITY')
        out.append({'part_no':name, 'quantity':int(qty), 'origin':origin, 'verification':'EXTRACTED_NOT_ENGINEERING_PROVED'})
    if not out or len(out)>MAX_PARTS: raise IntakeError('NO_VALID_BOM_OR_TOO_MANY_PARTS')
    c=Counter()
    for r in out:c[r['part_no']]+=r['quantity']
    return [{'part_no':k,'quantity':n,'origin':origin,'verification':'EXTRACTED_NOT_ENGINEERING_PROVED'} for k,n in sorted(c.items())]

def _dxf_ascii(data):
    try:s=data.decode('utf-8-sig')
    except UnicodeDecodeError:s=data.decode('cp1252')
    lines=s.replace('\r','').split('\n')
    if len(lines)%2:lines=lines[:-1]
    pairs=[]
    for i in range(0,len(lines),2):
        code=lines[i].strip()
        if not code.isdecimal():continue
        pairs.append((int(code),lines[i+1].strip()))
    # Only entities in ENTITIES section; block definitions are NOT real placements.
    state=None; inserts=[]; entity=None; fields=[]
    def flush():
        if entity!='INSERT':return
        named=[v for k,v in fields if k==2]
        if not named or named[0].startswith('*'):return
        name=named[0]; n=1
        for k,v in fields:
            if k in (70,71):
                try:n*=int(v)
                except ValueError:raise IntakeError('INVALID_DXF_ARRAY')
        if n<1 or n>100000:raise IntakeError('INVALID_DXF_ARRAY')
        inserts.append({'part_no':name,'qty':n})
    for i,(code,val) in enumerate(pairs):
        if code==0 and val=='SECTION':
            if state=='ENTITIES':flush()
            state=None;entity=None;fields=[]
        elif code==2 and state is None and i>0 and pairs[i-1]==(0,'SECTION'):
            state=val
        elif code==0 and val=='ENDSEC':
            if state=='ENTITIES':flush()
            state=None;entity=None;fields=[]
        elif state=='ENTITIES' and code==0:
            flush();entity=val;fields=[]
        elif state=='ENTITIES' and entity:fields.append((code,val))
    return _rows(inserts,'DXF_INSERT_ENTITY') if inserts else []

def _svg_annotations(data):
    root=ET.fromstring(data)
    if len(data)>MAX_BYTES:raise IntakeError('TOO_LARGE')
    rows=[]
    for element in root.iter():
        if len(rows)>MAX_PARTS:raise IntakeError('TOO_MANY_PARTS')
        p=element.attrib.get('data-part-number')
        if p:rows.append({'part_no':p,'qty':element.attrib.get('data-qty','1')})
    return _rows(rows,'SVG_EXPLICIT_BOM_ANNOTATION') if rows else []

def _pdf_text(data):
    try:
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data))
        if len(reader.pages)>30:raise IntakeError('TOO_MANY_PAGES')
        s='\n'.join(p.extract_text() or '' for p in reader.pages)
        rows=[{'part_no':n,'qty':q} for n,q in BOM_TEXT.findall(s)]
        return _rows(rows,'PDF_TEXT_BOM_ROWS') if rows else []
    except ImportError:return []
    except IntakeError:raise
    except Exception:raise IntakeError('UNREADABLE_PDF')

def extract(filename: str, data: bytes):
    if not isinstance(data,bytes) or not data or len(data)>MAX_BYTES:raise IntakeError('INVALID_SIZE_MAX_2MB')
    if '/' in filename or '\\' in filename or '\x00' in filename or len(filename)>200:raise IntakeError('INVALID_FILENAME')
    ext='.'+filename.rsplit('.',1)[-1].lower() if '.' in filename else ''
    if ext not in ALLOW:raise IntakeError('UNSUPPORTED_EXTENSION')
    sha=hashlib.sha256(data).hexdigest();rows=[]
    if ext=='.csv':
        try:rows=_rows(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))),'CSV_BOM')
        except UnicodeDecodeError:raise IntakeError('INVALID_ENCODING')
    elif ext=='.json':
        try:doc=json.loads(data);rows=_rows(doc['bom'] if isinstance(doc,dict) else doc,'JSON_BOM')
        except (ValueError,KeyError,TypeError) as e:raise IntakeError('INVALID_JSON_BOM') from e
    elif ext=='.dxf':rows=_dxf_ascii(data)
    elif ext=='.svg':
        try:rows=_svg_annotations(data)
        except ET.ParseError as e:raise IntakeError('INVALID_SVG') from e
    elif ext=='.pdf':rows=_pdf_text(data)
    # STEP/STL are geometry, not part/BOM evidence. No fictitious CAD understanding.
    status='T' if rows else 'Z'
    return {'schema':'legion.cad-bom-intake.v1','filename':filename,'file_sha256':sha,
            'format':ext[1:].upper(),'extraction':status,'bom':rows,
            'evidence_scope':'UNVERIFIED_DRAWING_LABELS_NOT_ENGINEERING_PROOF',
            'reason':'STRUCTURED_PARTS_EXTRACTED_REVIEW_REQUIRED' if rows else 'NO_BOM_EXTRACTABLE_MANUAL_BOM_REQUIRED',
            'raw_file_retained':False,'sent_to_suppliers':False}
