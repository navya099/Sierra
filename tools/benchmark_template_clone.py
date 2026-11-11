
import argparse
import copy
import io
import pickle
import statistics
import time

import ezdxf


def benchmark(name, factory, count):
    durations = []
    errors = []

    for _ in range(count):
        start = time.perf_counter()
        doc = factory()
        durations.append(time.perf_counter() - start)

        auditor = doc.audit()
        if auditor.errors:
            errors.append(len(auditor.errors))

    print(
        f"{name:16s} "
        f"total={sum(durations):.4f}s "
        f"mean={statistics.mean(durations):.4f}s "
        f"audit_errors={sum(errors)}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True)
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be positive")

    template = args.template
    count = args.count

    print("=== PROFILE-PERF1-P4-B-3-A ===")
    print(f"Template: {template}")
    print(f"Iterations: {count}")

    source = ezdxf.readfile(template)

    # P4-B-2 baseline: StringIO serialization + parsing.
    buffer = io.StringIO()
    source.write(buffer)
    template_text = buffer.getvalue()

    # Pickle serialization is measured separately.
    pickle_start = time.perf_counter()
    serialized = pickle.dumps(
        source,
        protocol=pickle.HIGHEST_PROTOCOL,
    )
    pickle_time = time.perf_counter() - pickle_start

    print(f"Pickle setup: {pickle_time:.4f}s")
    print(f"Pickle bytes: {len(serialized):,}")

    benchmark(
        "StringIO read",
        lambda: ezdxf.read(io.StringIO(template_text)),
        count,
    )

    benchmark(
        "deepcopy",
        lambda: copy.deepcopy(source),
        count,
    )

    benchmark(
        "pickle loads",
        lambda: pickle.loads(serialized),
        count,
    )

    # Verify that edits to a clone do not alter the source.
    original_count = len(source.modelspace())

    clone = copy.deepcopy(source)
    clone.modelspace().add_line(
        (0, 0),
        (123, 456),
        dxfattribs={"layer": "0"},
    )

    independent = (
        len(source.modelspace()) == original_count
        and len(clone.modelspace()) == original_count + 1
    )

    print(
        "Deepcopy modelspace independence:",
        "PASS" if independent else "FAIL",
    )

    if not independent:
        raise RuntimeError("Document independence failed")


if __name__ == "__main__":
    main()
