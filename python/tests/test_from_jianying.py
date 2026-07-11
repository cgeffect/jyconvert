"""剪映 draft_info → NGL 协议反向转换测试。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from protocol.from_jianying import (
    ReverseContext,
    convert_draft_to_protocol,
    extract_tracks_info,
    resolve_draft_media_path,
)

PLAIN_DRAFT = Path("/tmp/jyconvert_test/_test_plain/draft_info.json")
ORIG_PROTOCOL = Path(__file__).resolve().parent.parent.parent / "examples" / "converted_protocol" / "converted_protocol.json"
FONT = Path(__file__).resolve().parent.parent.parent / "examples" / "字制区喜脉体.ttf"


@unittest.skipUnless(PLAIN_DRAFT.exists(), "需要先生成明文剪映草稿: python/jianying/convert.py")
class ReverseConversionTest(unittest.TestCase):
    def test_round_trip_counts(self) -> None:
        draft_info = json.loads(PLAIN_DRAFT.read_text(encoding="utf-8"))
        ctx = ReverseContext(
            draft_dir=PLAIN_DRAFT.parent,
            output_dir=Path("/tmp/jyconvert_reverse_unit_test"),
            font_source=FONT,
        )
        protocol = convert_draft_to_protocol(draft_info, ctx)
        orig = json.loads(ORIG_PROTOCOL.read_text(encoding="utf-8"))

        self.assertEqual(protocol["duration"], orig["duration"])
        self.assertEqual(len(protocol["tracks"]), len(orig["tracks"]))
        for key in ("videos", "audios", "texts", "images"):
            self.assertEqual(len(protocol["materials"][key]), len(orig["materials"][key]))

        text = json.loads(protocol["materials"]["texts"][0]["content"])
        self.assertEqual(text["text"], "想喝精酿就选歪马送酒")
        self.assertAlmostEqual(text["styles"][0]["size"], 35.0, places=1)
        self.assertIn("字制区喜脉体", text["styles"][0]["font"]["path"])

    def test_tracks_only(self) -> None:
        draft_info = json.loads(PLAIN_DRAFT.read_text(encoding="utf-8"))
        info = extract_tracks_info(draft_info, PLAIN_DRAFT.parent)
        self.assertEqual(len(info["tracks"]), 7)
        self.assertEqual(info["duration_ms"], 23360)
        video_track = next(t for t in info["tracks"] if t["id"] == "track_video_0")
        self.assertEqual(video_track["segments"][0]["target_timerange"]["duration"], 2016)
        self.assertIn("name", video_track["segments"][0]["material"])


class DraftPathPlaceholderTest(unittest.TestCase):
    def test_resolve_text_reading_placeholder(self) -> None:
        draft_dir = Path("/Users/xy/Movies/CapCut/User Data/Projects/com.lveditor.draft/0709")
        if not draft_dir.is_dir():
            self.skipTest("本地无 CapCut 0709 草稿")
        raw = (
            "##_draftpath_placeholder_0E685133-18CE-45ED-8CB8-2904A212EC80_##/"
            "textReading/6a4f5ca1f09f7a01f971fc8a_8_0_2cfd2ab9-a2cf-460f-8e79-2b72059ae2b6.wav"
        )
        resolved = resolve_draft_media_path(raw, draft_dir)
        assert resolved is not None
        self.assertTrue(resolved.exists())
        self.assertEqual(resolved.parent.name, "textReading")


if __name__ == "__main__":
    unittest.main()
