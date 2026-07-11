#!/usr/bin/env python3
"""
一键转换并导入剪映（便捷脚本，等价于 convert.py + import_draft.py）。

推荐工作流（Chrome 生成 + Mac 导入）请分两步:
  python3 python/jianying/convert.py ...
  python3 python/jianying/import_draft.py --draft-dir ... --jianying-name ...

用法:
  cd jyconvert && python3 python/jianying/to_jianying.py \
    --protocol examples/converted_protocol/converted_protocol.json \
    --resource-root examples/converted_protocol \
    --name my_draft \
    --output-dir ~/Downloads \
    --jianying-name my_draft
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capcut.lib import summarize_draft
from jianying.convert_lib import convert_protocol_to_local_draft
from jianying.import_draft import import_draft_to_jianying
from jianying.lib import jianying_drafts_root


def main() -> None:
    parser = argparse.ArgumentParser(description="NGLEngine 协议 → 剪映草稿（一键）")
    parser.add_argument("--protocol", type=Path, required=True, help="协议 JSON 路径")
    parser.add_argument(
        "--resource-root",
        type=Path,
        default=None,
        help="可选；默认使用协议 JSON 所在目录",
    )
    parser.add_argument("--name", required=True, help="本地草稿目录名")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="本地草稿输出根目录",
    )
    parser.add_argument(
        "--jianying-name",
        required=True,
        help="导入后在剪映中显示的草稿名称",
    )
    parser.add_argument(
        "--jianying-drafts-root",
        type=Path,
        help="剪映草稿根目录（com.lveditor.draft）",
    )
    args = parser.parse_args()

    if not args.protocol.exists():
        raise FileNotFoundError(f"协议文件不存在: {args.protocol}")
    resource_root = (args.resource_root or args.protocol.parent).resolve()
    if not resource_root.exists():
        raise FileNotFoundError(f"资源根目录不存在: {resource_root}")

    print("=" * 60)
    print("NGLEngine 协议 → 剪映草稿（一键）")
    print("=" * 60)

    local_draft = convert_protocol_to_local_draft(
        protocol_path=args.protocol,
        resource_root=resource_root,
        draft_name=args.name,
        output_root=args.output_dir.resolve(),
    )
    summarize_draft(local_draft)

    dst = import_draft_to_jianying(
        local_draft,
        args.jianying_name,
        args.jianying_drafts_root,
    )
    summarize_draft(dst)

    print("\n✓ 完成")
    print(f"  本地草稿: {local_draft}")
    print(f"  剪映草稿: {dst}")
    print(f"  剪映草稿根目录: {jianying_drafts_root(args.jianying_drafts_root)}")


if __name__ == "__main__":
    main()
