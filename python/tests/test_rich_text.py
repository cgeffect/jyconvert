"""富文本协议 → 剪映/CapCut content 转换测试。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from protocol.converter import ConversionContext, convert_text_content, convert_text_material

EXAMPLE_ROOT = Path(__file__).resolve().parent.parent.parent / "examples" / "converted_protocol"
PROTOCOL = Path(__file__).resolve().parent.parent.parent.parent / "config" / "transition_protocol.json"


def make_ctx(target: str) -> ConversionContext:
    return ConversionContext(
        protocol_path=PROTOCOL,
        resource_root=EXAMPLE_ROOT,
        draft_dir=Path("/tmp/ngl_jyconvert_test_draft"),
        imported_dir=Path("/tmp/ngl_jyconvert_test_draft/Resources/imported"),
        fonts_dir=Path("/tmp/ngl_jyconvert_test_draft/Resources/fonts"),
        draft_id="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
        draft_target=target,  # type: ignore[arg-type]
    )


class RichTextConversionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.content_str = json.loads(PROTOCOL.read_text(encoding="utf-8"))["materials"]["texts"][0]["content"]

    def test_capcut_uses_utf16_ranges(self) -> None:
        ctx = make_ctx("capcut")
        out, _, rich = convert_text_content(self.content_str, ctx)
        self.assertTrue(rich)
        parsed = json.loads(out)
        self.assertEqual(parsed["styles"][0]["range"], [0, 12])
        self.assertEqual(parsed["styles"][1]["range"], [12, 20])

    def test_jianying_uses_char_ranges(self) -> None:
        ctx = make_ctx("jianying")
        out, _, rich = convert_text_content(self.content_str, ctx)
        self.assertTrue(rich)
        parsed = json.loads(out)
        self.assertEqual(parsed["text"], "想喝精酿就选歪马送酒")
        self.assertEqual(parsed["styles"][0]["range"], [0, 6])
        self.assertEqual(parsed["styles"][1]["range"], [6, 10])
        self.assertTrue(parsed["styles"][1].get("useLetterColor"))

    def test_jianying_material_flags(self) -> None:
        ctx = make_ctx("jianying")
        mat = convert_text_material(
            {"id": "material_text_0", "content": self.content_str, "alignment": 1},
            ctx,
        )
        assert mat is not None
        self.assertTrue(mat["is_rich_text"])
        self.assertFalse(mat["use_effect_default_color"])

    def test_capcut_material_flags(self) -> None:
        ctx = make_ctx("capcut")
        mat = convert_text_material(
            {"id": "material_text_0", "content": self.content_str, "alignment": 1},
            ctx,
        )
        assert mat is not None
        self.assertFalse(mat["is_rich_text"])
        self.assertTrue(mat["use_effect_default_color"])


if __name__ == "__main__":
    unittest.main()
