"""Compare generated combined plan/profile DXF sheets against a baseline."""

import argparse
from collections import Counter
from pathlib import Path

import ezdxf


IGNORED_DXF_ATTRIBUTES = {
    "handle",
    "owner",
}


def normalize(value):
    """Create a hashable, deterministic representation."""
    if isinstance(value, float):
        return round(value, 8)

    if isinstance(value, (str, int, bool, type(None))):
        return value

    if hasattr(value, "xyz"):
        return tuple(normalize(v) for v in value.xyz)

    if isinstance(value, (tuple, list)):
        return tuple(normalize(v) for v in value)

    if isinstance(value, dict):
        return tuple(sorted(
            (str(k), normalize(v))
            for k, v in value.items()
        ))

    return repr(value)


def entity_signature(ent):
    """Compare DXF entity geometry and attributes, ignoring identifiers."""
    attrs = {
        key: value
        for key, value in ent.dxf.all_existing_dxf_attribs().items()
        if key not in IGNORED_DXF_ATTRIBUTES
    }

    geometry = ()

    if ent.dxftype() == "LWPOLYLINE":
        geometry = (
            tuple(
                normalize(point)
                for point in ent.get_points("xyseb")
            ),
            bool(ent.closed),
        )

    elif ent.dxftype() == "POLYLINE":
        geometry = (
            tuple(
                normalize(vertex.dxf.all_existing_dxf_attribs())
                for vertex in ent.vertices
            ),
            bool(ent.is_closed),
        )

    elif ent.dxftype() == "INSERT":
        geometry = tuple(
            entity_signature(child)
            for child in ent.attribs
        )

    return (
        ent.dxftype(),
        normalize(attrs),
        normalize(geometry),
    )


def inspect_dxf(path):
    doc = ezdxf.readfile(str(path))

    auditor = doc.audit()
    errors = len(auditor.errors)

    signatures = Counter(
        entity_signature(ent)
        for ent in doc.modelspace()
    )

    return signatures, errors


def compare_directories(baseline, candidate):
    baseline = Path(baseline).resolve()
    candidate = Path(candidate).resolve()

    if not baseline.is_dir():
        raise ValueError(f"기준 폴더가 없습니다: {baseline}")

    if not candidate.is_dir():
        raise ValueError(f"비교 폴더가 없습니다: {candidate}")

    if baseline == candidate:
        raise ValueError("기준 폴더와 비교 폴더가 동일합니다.")

    base_files = {p.name: p for p in baseline.glob("*.dxf")}
    cand_files = {p.name: p for p in candidate.glob("*.dxf")}

    print("=" * 72)
    print("R4-6 DXF REGRESSION CHECK")
    print("=" * 72)
    print(f"BASELINE : {baseline}")
    print(f"CANDIDATE: {candidate}")
    print(f"FILES    : {len(base_files)} / {len(cand_files)}")

    missing = sorted(base_files.keys() - cand_files.keys())
    extra = sorted(cand_files.keys() - base_files.keys())

    failures = 0

    if missing:
        print(f"[FAIL] 누락된 파일: {missing}")
        failures += len(missing)

    if extra:
        print(f"[FAIL] 추가된 파일: {extra}")
        failures += len(extra)

    total_base = 0
    total_cand = 0
    total_audit_errors = 0
    total_difference = 0

    for name in sorted(base_files.keys() & cand_files.keys()):
        try:
            a, audit_a = inspect_dxf(base_files[name])
            b, audit_b = inspect_dxf(cand_files[name])

            count_a = sum(a.values())
            count_b = sum(b.values())

            total_base += count_a
            total_cand += count_b
            total_audit_errors += audit_a + audit_b

            removed = a - b
            added = b - a

            difference = sum(removed.values()) + sum(added.values())
            total_difference += difference

            if difference or audit_a or audit_b:
                failures += 1
                print(
                    f"[FAIL] {name}: "
                    f"entities={count_a}/{count_b}, "
                    f"diff={difference}, "
                    f"audit={audit_a}/{audit_b}"
                )

                for label, values in (
                    ("BASELINE ONLY", removed),
                    ("CANDIDATE ONLY", added),
                ):
                    for signature, count in values.most_common(3):
                        print(
                            f"  {label} x{count}: "
                            f"{str(signature)[:220]}"
                        )
            else:
                print(f"[PASS] {name}: {count_a} entities")

        except Exception as exc:
            failures += 1
            print(f"[ERROR] {name}: {type(exc).__name__}: {exc}")

    print("=" * 72)
    print(f"기준 엔티티 합계 : {total_base:,}")
    print(f"비교 엔티티 합계 : {total_cand:,}")
    print(f"형상·속성 차이   : {total_difference:,}")
    print(f"DXF Audit 오류  : {total_audit_errors:,}")
    print(f"실패 항목       : {failures:,}")
    print("=" * 72)

    if failures:
        print("[FAIL] DXF 회귀 검증 실패")
        return 1

    print("[PASS] DXF 전체 회귀 검증 완료")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Compare generated combined plan/profile DXF sheets."
    )
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)

    args = parser.parse_args()

    try:
        return compare_directories(args.baseline, args.candidate)
    except (ValueError, OSError) as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
