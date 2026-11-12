"""Read a real STEP assembly with OpenCascade XCAF and report its component structure.

Only observed facts are emitted: product names, instance counts, per-definition topology,
bounding box and volume in the file's own length unit. Nothing is inferred (no material,
no tolerance, no manufacturing process) - those come only from named source documents.

Root cause of the earlier F_OCCT_EXCEPTION (CAD027 repair run 20261111_220944): with
cadquery-ocp 8.x, ``Bnd_Box.Get()`` returns the C++ struct ``Bnd_Box::Limits`` which has no
Python binding ("Unregistered type : Bnd_Box::Limits"). The import itself had succeeded.
This module reads the box through ``CornerMin()`` / ``CornerMax()`` instead.
"""
from __future__ import annotations

import collections
import hashlib
import re
from pathlib import Path


class SourceMismatch(ValueError):
    """The file is not the pinned source (wrong SHA-256)."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fp:
        while block := fp.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def step_length_unit(path: Path) -> str:
    """Length unit declared in the STEP header/data (text scan of SI_UNIT for LENGTH_UNIT)."""
    head = Path(path).read_bytes()
    m = re.search(rb"LENGTH_UNIT\(\)\s*NAMED_UNIT\(\*\)\s*SI_UNIT\(\s*(\.[A-Z]+\.|\$)\s*,\s*\.METRE\.", head)
    if not m:
        return "UNKNOWN"
    prefix = m.group(1).decode().strip(".")
    return {"MILLI": "mm", "CENTI": "cm", "$": "m"}.get(prefix, prefix.lower() + "metre")


def bbox(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box, True)
    if box.IsVoid():
        return None
    lo, hi = box.CornerMin(), box.CornerMax()   # NOT box.Get(): see module docstring
    return [round(hi.X() - lo.X(), 3), round(hi.Y() - lo.Y(), 3), round(hi.Z() - lo.Z(), 3)]


def topology(shape):
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE
    out = {}
    for kind, name in ((TopAbs_SOLID, "solids"), (TopAbs_FACE, "faces")):
        ex, n = TopExp_Explorer(shape, kind), 0
        while ex.More():
            n += 1
            ex.Next()
        out[name] = n
    return out


def volume(shape):
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return round(float(props.Mass()), 3)


def read_assembly(path: Path, expected_sha256: str | None = None, geometry: bool = True) -> dict:
    """Return the XCAF component tree summary of ``path``. Raises SourceMismatch on a wrong SHA."""
    path = Path(path)
    digest = sha256_file(path)  # checked before anything else, including loading OpenCascade
    if expected_sha256 and digest != expected_sha256:
        raise SourceMismatch(f"SHA256_MISMATCH expected {expected_sha256} got {digest}")
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TDocStd import TDocStd_Document
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool
    from OCP.TDF import TDF_Label
    try:  # cadquery-ocp >= 8 binds NCollection sequences under OCP.collections
        from OCP.OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
    except ImportError:  # older OCP
        from OCP.TDF import TDF_LabelSequence
    from OCP.TDataStd import TDataStd_Name
    from OCP.IFSelect import IFSelect_RetDone

    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        return {"verdict": "F_STEPCAF_READ", "read_status": int(status), "sha256": digest}
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    if not reader.Transfer(doc):
        return {"verdict": "F_STEPCAF_TRANSFER", "sha256": digest}
    tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    def name_of(label):
        attr = TDataStd_Name()
        if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
            return attr.Get().ToExtString().strip()
        return None

    roots = TDF_LabelSequence()
    tool.GetFreeShapes(roots)
    instances = collections.Counter()      # leaf product name -> instance count in the whole tree
    paths = collections.defaultdict(list)  # leaf product name -> parent assembly names (one per instance)
    definitions = {}                       # leaf product name -> geometry of its definition
    stats = {"assemblies": 0, "occurrences": 0, "max_depth": 0}

    def descend(label, depth, chain):
        stats["max_depth"] = max(stats["max_depth"], depth)
        if depth > 80:
            raise RuntimeError("ASSEMBLY_DEPTH_BOUND")
        stats["assemblies"] += 1
        children = TDF_LabelSequence()
        XCAFDoc_ShapeTool.GetComponents_s(label, children, False)
        for i in range(1, children.Length() + 1):
            child, target = children.Value(i), TDF_Label()
            if not XCAFDoc_ShapeTool.GetReferredShape_s(child, target):
                raise RuntimeError("UNRESOLVED_COMPONENT_REFERENCE")
            stats["occurrences"] += 1
            pname = name_of(target) or name_of(child) or "UNNAMED"
            if XCAFDoc_ShapeTool.IsAssembly_s(target):
                descend(target, depth + 1, chain + [pname])
            else:
                instances[pname] += 1
                paths[pname].append("/".join(chain))
                if geometry and pname not in definitions:
                    shape = XCAFDoc_ShapeTool.GetShape_s(target)
                    definitions[pname] = None if shape.IsNull() else {
                        **topology(shape), "bbox": bbox(shape), "volume": volume(shape)}

    root_names = []
    for i in range(1, roots.Length() + 1):
        root = roots.Value(i)
        rname = name_of(root) or "UNNAMED_ROOT"
        root_names.append(rname)
        if XCAFDoc_ShapeTool.IsAssembly_s(root):
            descend(root, 0, [rname])
        else:
            instances[rname] += 1
    return {
        "schema": "legion.cad.xcaf.v1",
        "verdict": "T_XCAF_STRUCTURE" if instances else "F_EMPTY_ASSEMBLY",
        "file": path.name, "bytes": path.stat().st_size, "sha256": digest,
        "length_unit": step_length_unit(path),
        "roots": root_names, **stats,
        "leaf_definitions": len(instances), "leaf_instances": sum(instances.values()),
        "instances": dict(sorted(instances.items())),
        "parents": {k: dict(collections.Counter(v)) for k, v in sorted(paths.items())},
        "geometry": definitions,
        "inferred_fields": [],
    }
