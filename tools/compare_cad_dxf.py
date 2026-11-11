
from pathlib import Path
from collections import Counter
import argparse
import ezdxf


def signature(ent):
    attrs = ent.dxf.all_existing_dxf_attribs().copy()

    for key in ("handle", "owner"):
        attrs.pop(key, None)

    points = (
        list(ent.get_points())
        if ent.dxftype() == "LWPOLYLINE"
        else None
    )

    return (
        ent.dxftype(),
        repr(sorted(attrs.items())),
        repr(points),
    )


def compare_dxf_folders(before, after, expected_sheets=20):
    before = Path(before)
    after = Path(after)

    if not before.is_dir():
        raise FileNotFoundError(before)

    if not after.is_dir():
        raise FileNotFoundError(after)

    a_files = {p.name: p for p in before.glob("*.dxf")}
    b_files = {p.name: p for p in after.glob("*.dxf")}

    if a_files.keys() != b_files.keys():
        missing = sorted(a_files.keys() - b_files.keys())
        extra = sorted(b_files.keys() - a_files.keys())
        raise AssertionError(
            f"DXF filenames differ: missing={missing}, extra={extra}"
        )

    if len(a_files) != expected_sheets:
        raise AssertionError(
            f"Expected {expected_sheets} sheets, got {len(a_files)}"
        )

    total_entities = 0

    for name in sorted(a_files):
        doc_a = ezdxf.readfile(a_files[name])
        doc_b = ezdxf.readfile(b_files[name])

        ca = Counter(signature(e) for e in doc_a.modelspace())
        cb = Counter(signature(e) for e in doc_b.modelspace())

        if ca != cb:
            missing = ca - cb
            extra = cb - ca

            print(f"[FAIL] {name}")
            print(f"  Missing signatures: {sum(missing.values())}")
            print(f"  Extra signatures: {sum(extra.values())}")

            raise AssertionError(f"CAD entities differ: {name}")

        count = sum(ca.values())
        total_entities += count

        print(f"[PASS] {name}: {count} entities identical")

    print("-" * 60)
    print(f"[PASS] All {len(a_files)} DXF modelspaces identical")
    print(f"[PASS] Total entities compared: {total_entities}")
    print("[PASS] CAD regression")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare DXF modelspace entities between two folders"
    )

    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--expected-sheets", type=int, default=20)

    args = parser.parse_args()

    compare_dxf_folders(
        args.before,
        args.after,
        args.expected_sheets,
    )
