"""Pinned pmix JSON bridge, not a CAD parser or engineering authority.

Linux x86-64 only. bubblewrap is mandatory: no network, no host data mounts,
private scratch, read-only runtime/binary, CPU/address-space/file limits. A
missing dependency or failed sandbox yields visible Z; never an unsafe fallback.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import threading

VERSION = '0.16.1'
BINARY_SHA256 = 'cc44b80916fd03c03b74bfa5b011061583c2b96cfc0ca0685ca93cfe1ca0ae43'
MAX_BYTES = 16 * 1024 * 1024
MAX_OUTPUT = 32 * 1024 * 1024
TIMEOUT = 20
MAX_PARTS = 300
MAX_OCCURRENCES = 100000
_SLOTS = threading.BoundedSemaphore(2)
_REF = re.compile(r'#\d+\Z')


class PmixError(ValueError):
    pass


def _binary():
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise PmixError('PMIX_REQUIRES_LINUX_X86_64_SANDBOX')
    path = Path(os.environ.get('LEGION_PMIX_BINARY', 'external/pmix/pmix')).resolve()
    if not path.is_file():
        raise PmixError('PMIX_BINARY_MISSING')
    if path.stat().st_size > 64 * 1024 * 1024:
        raise PmixError('PMIX_BINARY_SIZE_INVALID')
    if hashlib.sha256(path.read_bytes()).hexdigest() != BINARY_SHA256:
        raise PmixError('PMIX_BINARY_CHECKSUM_MISMATCH')
    return path


def _run(binary, folder, command):
    """No shell; file outputs and stderr are OS-bounded before JSON decoding."""
    bwrap, prlimit = shutil.which('bwrap'), shutil.which('prlimit')
    if not bwrap or not prlimit:
        raise PmixError('PMIX_SANDBOX_DEPENDENCY_MISSING')
    output = folder / (command + '.json')
    argv = [prlimit, '--as=1073741824', '--cpu=10', f'--fsize={MAX_OUTPUT}',
            '--nofile=64', '--core=0', '--', bwrap, '--die-with-parent',
            '--unshare-all', '--new-session', '--cap-drop', 'ALL',
            '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib',
            '--ro-bind-try', '/lib64', '/lib64', '--proc', '/proc',
            '--dev', '/dev', '--tmpfs', '/tmp', '--dir', '/app',
            '--ro-bind', str(binary), '/app/pmix',
            '--bind', str(folder), '/work', '--chdir', '/work',
            '--clearenv', '--setenv', 'HOME', '/tmp', '--setenv', 'LANG', 'C',
            '/app/pmix', command, '/work/input.stp']
    if command == 'product':
        argv.append('--json')
    argv += ['--output', '/work/' + output.name]
    with (folder / (command + '.stderr')).open('wb') as err:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                stdout=err, stderr=err, start_new_session=True,
                                env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
        try:
            proc.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            raise PmixError('PMIX_TIMEOUT') from exc
    stderr = (folder / (command + '.stderr')).read_bytes()[:8192].decode('utf-8', 'replace')
    if proc.returncode != 0:
        raise PmixError('PMIX_' + command.upper() + '_FAILED: ' + stderr[:2000])
    if not output.is_file() or output.stat().st_size > MAX_OUTPUT:
        raise PmixError('PMIX_OUTPUT_LIMIT_OR_MISSING')
    try:
        doc = json.loads(output.read_bytes(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError, RecursionError) as exc:
        raise PmixError('PMIX_INVALID_JSON') from exc
    if not isinstance(doc, dict) or doc.get('schema_version') != 1:
        raise PmixError('PMIX_UNSUPPORTED_OUTPUT_SCHEMA')
    return doc, stderr


def _field(value=None, refs=(), sha=None):
    return {'value': value, 'extraction': 'T' if value is not None and refs else 'Z',
            'engineering_verdict': 'Z', 'file_sha256': sha, 'source_refs': list(refs)}


def adapt(raw, extracted, product):
    """Map pmix-owned semantics; never parse or infer engineering from STEP text.

    The only STEP scan checks that pmix's #entity references exist. PMI remains
    document-scoped unless pmix supplies an unambiguous part/occurrence label.
    """
    sha = hashlib.sha256(raw).hexdigest()
    declared = {'#' + n.decode() for n in re.findall(rb'(?:^|\n)\s*#(\d+)\s*=', raw)}

    def provenance(record):
        refs = record.get('source_refs') or []
        if not isinstance(refs, list) or any(not isinstance(r, str) for r in refs):
            raise PmixError('INVALID_SOURCE_REFERENCES')
        if any(_REF.fullmatch(r) and r not in declared for r in refs):
            raise PmixError('SOURCE_ENTITY_NOT_DECLARED')
        return refs

    def annotate(obj):
        if isinstance(obj, dict):
            out = {k: annotate(v) for k, v in obj.items()}
            if 'source_refs' in obj:
                provenance(obj)
                out.update(file_sha256=sha, engineering_verdict='Z')
            return out
        if isinstance(obj, list):
            return [annotate(x) for x in obj]
        return obj

    extracted, product = annotate(extracted), annotate(product)
    parts = product.get('parts') or []
    if len(parts) > MAX_PARTS:
        raise PmixError('TOO_MANY_PARTS')
    indexed = {p['id']: p for p in parts}
    if len(indexed) != len(parts):
        raise PmixError('DUPLICATE_PART_ID')
    relations = product.get('relations') or []
    children = defaultdict(list)
    occurrence_names = defaultdict(set)
    for rel in relations:
        if rel.get('parent') not in indexed or rel.get('child') not in indexed:
            raise PmixError('ASSEMBLY_PART_NOT_DECLARED')
        children[rel['parent']].append(rel)
        if rel.get('name'):
            occurrence_names[rel['child']].add(rel['name'])
    roots = product.get('roots') or [p for p in indexed if not any(r['child'] == p for r in relations)]
    if indexed and not roots:
        raise PmixError('CYCLE_OR_MISSING_ASSEMBLY_ROOT')
    memo = {}

    def leaves(pid, stack=()):
        if pid not in indexed:
            raise PmixError('ASSEMBLY_PART_NOT_DECLARED')
        if pid in stack or len(stack) > 64:
            raise PmixError('CYCLE_OR_ASSEMBLY_DEPTH_LIMIT')
        if pid in memo:
            return memo[pid]
        counts = Counter()
        if not children[pid]:
            counts[pid] = 1
        for rel in children[pid]:
            counts.update(leaves(rel['child'], stack + (pid,)))
        if sum(counts.values()) > MAX_OCCURRENCES:
            raise PmixError('ASSEMBLY_QUANTITY_LIMIT')
        memo[pid] = counts
        return counts

    # Validate disconnected subgraphs as well; never conceal a missing/cyclic use.
    for pid in indexed:
        leaves(pid)
    quantities = Counter()
    for root in roots:
        quantities.update(leaves(root))
    if sum(quantities.values()) > MAX_OCCURRENCES:
        raise PmixError('ASSEMBLY_QUANTITY_LIMIT')
    properties = extracted.get('properties') or []
    lines = []
    for pid, qty in sorted(quantities.items()):
        part = indexed[pid]
        refs = provenance(part)
        labels = {pid, part.get('name'), part.get('number')} | occurrence_names[pid]
        # Labels shared across distinct parts are not sufficient association evidence.
        labels -= {label for other in parts if other['id'] != pid
                   for label in ({other.get('name'), other.get('number')} | occurrence_names[other['id']])
                   if label in labels}
        props = [p for p in properties if p.get('part') in labels and p.get('part') is not None]

        def explicit(names, fallback=None):
            matches = [p for p in props if str(p.get('name', '')).casefold() in names
                       and provenance(p) and (p.get('value') or {}).get('value') is not None]
            values = {json.dumps(p['value']['value'], sort_keys=True) for p in matches}
            if len(values) == 1:
                return _field(matches[0]['value']['value'],
                              sorted({r for p in matches for r in provenance(p)}), sha)
            return _field(fallback, refs if fallback is not None else (), sha)

        revision = explicit({'revision', 'rev', 'revision_id'}, part.get('revision'))
        material = explicit({'material', 'material_name'})
        process = explicit({'process', 'manufacturing_process'})
        quantity_refs = sorted(set(refs + [r for rel in relations
                                         for r in provenance(rel)]))
        fields = {'part_no': _field(part.get('number'), refs, sha),
                  'revision': revision, 'material': material, 'process': process,
                  'quantity': _field(qty, quantity_refs, sha)}
        lines.append({'part_id': pid, 'part_no': part.get('number'),
                      'description': part.get('name'), 'quantity': qty,
                      'revision': revision['value'], 'material': material['value'],
                      'process': process['value'], 'fields': fields,
                      'properties': props, 'source_refs': refs, 'file_sha256': sha,
                      'origin': 'PMIX_STEP_PRODUCT', 'verification': 'EXTRACTED_NOT_ENGINEERING_PROVED',
                      'engineering_verdict': 'Z', 'procurement_eligible': False})
    return {'schema': 'legion.pmix-engineering.v1', 'parser': 'pmix ' + VERSION,
            'parser_sha256': BINARY_SHA256, 'file_sha256': sha,
            'bom': lines, 'assembly': product, 'engineering': extracted,
            'units': extracted.get('units') or {},
            'pmi_association': 'DOCUMENT_SCOPE_NOT_AUTOMATIC_PART_QUALIFICATION',
            'engineering_verdict': 'Z', 'production_qualification': 'Z',
            'procurement_eligible': False, 'checkout_enabled': False,
            'payment_effects': 0, 'supplier_effects': 0,
            'source_ref_scheme': 'STEP_P21_ENTITY_NUMBER_IN_ORIGINAL_FILE'}


def extract(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES:
        raise PmixError('INVALID_STEP_SIZE_MAX_16MB')
    if not _SLOTS.acquire(blocking=False):
        raise PmixError('PMIX_BUSY')
    try:
        binary = _binary()
        with tempfile.TemporaryDirectory(prefix='legion-pmix-') as tmp:
            folder = Path(tmp)
            (folder / 'input.stp').write_bytes(data)
            engineering, extract_log = _run(binary, folder, 'extract')
            product, product_log = _run(binary, folder, 'product')
            result = adapt(data, engineering, product)
            result['parser_stderr'] = {'extract': extract_log, 'product': product_log}
            return result
    except OSError as exc:
        raise PmixError('PMIX_OS_EXECUTION_ERROR_' + str(exc.errno)) from exc
    except (KeyError, TypeError, RecursionError) as exc:
        raise PmixError('INVALID_PMIX_STRUCTURE') from exc
    finally:
        _SLOTS.release()
