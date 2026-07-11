"""协议媒体路径解析测试。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from protocol.path_resolver import resolve_protocol_path


class ProtocolPathResolverTest(unittest.TestCase):
    def test_assets_relative_to_protocol_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "assets").mkdir()
            media = root / "assets" / "clip.mp4"
            media.write_bytes(b"x")
            resolved = resolve_protocol_path("./assets/clip.mp4", root)
            self.assertEqual(resolved, media.resolve())

    def test_custom_subdir_relative_to_protocol_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "abc").mkdir()
            media = root / "abc" / "clip.mp4"
            media.write_bytes(b"x")
            resolved = resolve_protocol_path("./abc/clip.mp4", root)
            self.assertEqual(resolved, media.resolve())

    def test_nested_protocol_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            protocol_dir = root / "pkg" / "configs"
            (protocol_dir / "abc").mkdir(parents=True)
            media = protocol_dir / "abc" / "clip.mp4"
            media.write_bytes(b"x")
            resolved = resolve_protocol_path("./abc/clip.mp4", protocol_dir)
            self.assertEqual(resolved, media.resolve())


if __name__ == "__main__":
    unittest.main()
