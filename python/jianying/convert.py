#!/usr/bin/env python3
"""
步骤 1：将 NGLEngine 协议转为剪映草稿格式，输出到本地目录。

此步骤不访问剪映安装目录，可在 Python / Node / 浏览器等任意环境生成草稿包，
再拷贝到 Mac 后由 import_draft.py 导入剪映。

用法:
  cd jyconvert && python3 python/jianying/convert.py \
    --protocol examples/converted_protocol/converted_protocol.json \
    --resource-root examples/converted_protocol \
    --name my_draft \
    --output-dir ~/Downloads
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capcut.lib import summarize_draft
from jianying.convert_lib import convert_protocol_to_local_draft


def main() -> None:
    parser = argparse.ArgumentParser(description="NGLEngine 协议 → 本地剪映草稿（步骤 1/2）")
    parser.add_argument("--protocol", type=Path, required=True, help="协议 JSON 路径")
    parser.add_argument(
        "--resource-root",
        type=Path,
        default=None,
        help="可选；媒体资源根目录。默认使用协议 JSON 所在目录（协议内 ./assets/、./abc/ 等相对它解析）",
    )
    parser.add_argument("--name", required=True, help="本地草稿目录名")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="输出根目录（草稿写入 output-dir/name/）",
    )
    args = parser.parse_args()

    if not args.protocol.exists():
        raise FileNotFoundError(f"协议文件不存在: {args.protocol}")
    resource_root = (args.resource_root or args.protocol.parent).resolve()
    if not resource_root.exists():
        raise FileNotFoundError(f"资源根目录不存在: {resource_root}")

    output_root = args.output_dir.resolve()

    print("=" * 60)
    print("NGLEngine 协议 → 本地剪映草稿（步骤 1/2）")
    print("=" * 60)

    draft_dir = convert_protocol_to_local_draft(
        protocol_path=args.protocol,
        resource_root=resource_root,
        draft_name=args.name,
        output_root=output_root,
    )

    summarize_draft(draft_dir)
    print("\n✓ 转换完成")
    print(f"  本地草稿: {draft_dir}")
    print(f"  输出根目录: {output_root.resolve()}")
    print("\n下一步（Mac 本地）:")
    print(
        f'  python3 python/jianying/import_draft.py '
        f'--draft-dir "{draft_dir}" --jianying-name <剪映草稿名>'
    )


if __name__ == "__main__":
    main()
