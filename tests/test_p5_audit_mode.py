import contextlib
import io
import inspect
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import ezdxf
from ezdxf.document import Drawing

from combined_plan_profile import combined_plan_profile_v1_7_core as core


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "test" / "cad"
TEMPLATE = ASSETS / "도각.dxf"
PLAN = ASSETS / "본선평면선형.dxf"


class TestP5AuditMode(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        for path in (TEMPLATE, PLAN):
            if not path.is_file():
                raise FileNotFoundError(
                    f"P5-C-1 테스트 입력 파일 없음: {path}"
                )

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_root = Path(self.temp_dir.name)

    def generate_one_sheet(self, mode=None, folder="output"):
        kwargs = {
            "station_origin": 0,
            "start_sta": 0,
            "end_sta": 700,
            "sheet_length": 700,
            "horizontal_scale": 1000,
            "vertical_scale": 400,
            "drawing_mode": core.DrawingMode.CAD,
        }

        if mode is not None:
            kwargs["audit_mode"] = mode

        output = self.output_root / folder

        list(core.generate(
            TEMPLATE,
            PLAN,
            output,
            **kwargs,
        ))

        files = sorted(output.glob("*.dxf"))
        self.assertEqual(len(files), 1)

        return files[0]

    def trace_generation(self, mode):
        events = []

        original_saveas = Drawing.saveas
        original_audit = Drawing.audit
        original_readfile = ezdxf.readfile

        def save_spy(doc, *args, **kwargs):
            events.append(("save", id(doc)))
            return original_saveas(doc, *args, **kwargs)

        def audit_spy(doc, *args, **kwargs):
            events.append(("audit", id(doc)))
            return original_audit(doc, *args, **kwargs)

        def read_spy(filename, *args, **kwargs):
            doc = original_readfile(filename, *args, **kwargs)
            events.append(("read", id(doc)))
            return doc

        with (
            patch.object(Drawing, "saveas", new=save_spy),
            patch.object(Drawing, "audit", new=audit_spy),
            patch.object(core.ezdxf, "readfile", new=read_spy),
        ):
            self.generate_one_sheet(mode, folder=f"trace_{mode}")

        return events

    def test_01_default_mode_is_file(self):
        signature = inspect.signature(core.generate)

        self.assertEqual(
            signature.parameters["audit_mode"].default,
            "file",
        )

        self.generate_one_sheet(folder="default")


    def test_02_file_mode_audit_order(self):
        events = self.trace_generation("file")
        names = [name for name, _ in events]

        # FILE: 저장 후 재로딩한 문서를 감사해야 한다.
        save_index = names.index("save")

        self.assertEqual(
            names[save_index:],
            ["save", "read", "audit"],
        )

        # 감사 대상은 저장 후 재로딩한 문서.
        self.assertEqual(
            events[save_index + 1][1],
            events[save_index + 2][1],
        )

        # 저장 전에 감사하면 안 된다.
        self.assertNotIn("audit", names[:save_index])

    def test_03_memory_mode_audit_order(self):
        events = self.trace_generation("memory")
        names = [name for name, _ in events]

        # MEMORY: 메모리 감사 후 저장해야 한다.
        audit_index = names.index("audit")

        self.assertEqual(
            names[audit_index:],
            ["audit", "save"],
        )

        # 감사한 문서와 저장한 문서가 동일해야 한다.
        self.assertEqual(
            events[audit_index][1],
            events[audit_index + 1][1],
        )

        # 저장 후 DXF를 재로딩하면 안 된다.
        self.assertNotIn("read", names[audit_index:])


    def test_04_invalid_audit_mode(self):
        with self.assertRaises(ValueError):
            list(core.generate(
                TEMPLATE,
                PLAN,
                self.output_root / "invalid",
                audit_mode="invalid",
            ))

    def test_05_file_memory_cad_equivalence(self):
        file_path = self.generate_one_sheet(
            "file", folder="file"
        )
        memory_path = self.generate_one_sheet(
            "memory", folder="memory"
        )

        file_doc = ezdxf.readfile(file_path)
        memory_doc = ezdxf.readfile(memory_path)

        self.assertFalse(file_doc.audit().errors)
        self.assertFalse(memory_doc.audit().errors)

        def entity_snapshot(doc):
            result = []

            for entity in doc.modelspace():
                attrs = entity.dxf.all_existing_dxf_attribs()
                attrs.pop("handle", None)
                attrs.pop("owner", None)

                geometry = None
                if entity.dxftype() == "LWPOLYLINE":
                    geometry = tuple(
                        tuple(point)
                        for point in entity.get_points("xyseb")
                    )

                result.append((
                    entity.dxftype(),
                    repr(sorted(attrs.items())),
                    repr(geometry),
                ))

            return Counter(result)

        self.assertEqual(
            entity_snapshot(file_doc),
            entity_snapshot(memory_doc),
        )


    def test_06_audit_log_hidden_by_default(self):
        buffer = io.StringIO()

        with contextlib.redirect_stdout(buffer):
            self.generate_one_sheet(
                "memory",
                folder="log_hidden",
            )

        output = buffer.getvalue()

        self.assertNotIn("[DXF AUDIT]", output)
        self.assertNotIn("[P5-B-2]", output)

    def test_07_audit_debug_log_enabled(self):
        buffer = io.StringIO()

        with contextlib.redirect_stdout(buffer):
            list(core.generate(
                TEMPLATE,
                PLAN,
                self.output_root / "log_enabled",
                station_origin=0,
                start_sta=0,
                end_sta=700,
                sheet_length=700,
                horizontal_scale=1000,
                vertical_scale=400,
                drawing_mode=core.DrawingMode.CAD,
                audit_mode="memory",
                audit_debug=True,
            ))

        output = buffer.getvalue()

        self.assertIn("[DXF AUDIT][memory]", output)
        self.assertIn("감사=", output)
        self.assertIn("저장=", output)


if __name__ == "__main__":
    unittest.main()
