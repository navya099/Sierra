
from pathlib import Path
from collections import Counter
import ezdxf

before = Path(r"C:\Temp\PROFILE-PERF1-P4B2")
after = Path(r"C:\Temp\PROFILE-PERF1-P4B3")

def signature(path):
    doc = ezdxf.readfile(str(path))
    blocks = {}
    for block in doc.blocks:
        blocks[block.name] = Counter(
            e.dxftype() for e in block
        )

    inserts = []
    for layout in doc.layouts:
        for entity in layout:
            if entity.dxftype() == "INSERT":
                attrs = tuple(sorted(
                    (a.dxf.tag, a.dxf.text)
                    for a in entity.attribs
                ))
                inserts.append((
                    layout.name,
                    entity.dxf.name,
                    attrs,
                ))

    return blocks, Counter(inserts)

files = sorted(before.glob("종평면도(*).dxf"))

assert len(files) == 20, f"Expected 20 files, got {len(files)}"

for path in files:
    target = after / path.name
    assert target.exists(), f"Missing: {target}"
    assert signature(path) == signature(target), path.name
    print("[PASS]", path.name)

print("[PASS] 20/20 block and attribute comparison")
