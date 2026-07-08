"""URL 提取单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.extract import extract_urls, pick_best_url


MOBILE_SHARE = (
    "9.28 复制打开抖音，看看【Zen的作品】营造网感的几种口播画面处理方式 # 口播剪辑 # ... "
    "https://v.douyin.com/wi_0Wcyj-l4/ ipq:/ :4pm D@h.bA 11/27"
)

WEB_SHARE = (
    "6.43 ytr:/ :7pm g@B.Tl 04/02 世界最最神秘最坚固的末日核地堡 价值超过10亿美元的世界最昂贵核地堡。"
    "从1美元的地堡到最贵地堡应有尽有# 野兽先生 # mrbeast # 末日地堡  "
    "https://v.douyin.com/yQbK5iC3VwM/ 复制此链接，打开Dou音搜索，直接观看视频！"
)


class ExtractUrlTests(unittest.TestCase):
    def test_mobile_share_text(self) -> None:
        urls = extract_urls(MOBILE_SHARE)
        self.assertEqual(urls, ["https://v.douyin.com/wi_0Wcyj-l4/"])

    def test_web_share_text(self) -> None:
        urls = extract_urls(WEB_SHARE)
        self.assertEqual(urls, ["https://v.douyin.com/yQbK5iC3VwM/"])

    def test_pick_best_url(self) -> None:
        self.assertEqual(pick_best_url(MOBILE_SHARE), "https://v.douyin.com/wi_0Wcyj-l4/")

    def test_plain_url(self) -> None:
        self.assertEqual(extract_urls("https://v.douyin.com/abc123/"), ["https://v.douyin.com/abc123/"])

    def test_empty(self) -> None:
        self.assertEqual(extract_urls(""), [])
        self.assertIsNone(pick_best_url("没有链接"))


if __name__ == "__main__":
    unittest.main()
