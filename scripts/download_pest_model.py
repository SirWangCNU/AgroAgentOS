#!/usr/bin/env python3
"""下载病虫害 YOLO ONNX 模型到 models/ 目录.

用法:
  python scripts/download_pest_model.py [--repo REPO_ID] [--filename FILENAME]

默认从 HuggingFace 下载, 需要安装 huggingface_hub:
  pip install huggingface_hub

环境变量:
  HUGGINGFACE_MODEL_REPO - HuggingFace 模型仓库 ID (如 user/yolov8-pest-detection)
  HUGGINGFACE_MODEL_FILE - 仓库中的文件名 (默认 best.onnx)
"""

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="下载病虫害 YOLO ONNX 模型")
    parser.add_argument(
        "--repo",
        default=os.environ.get("HUGGINGFACE_MODEL_REPO", ""),
        help="HuggingFace 模型仓库 ID (如 user/yolov8-pest-detection)",
    )
    parser.add_argument(
        "--filename",
        default=os.environ.get("HUGGINGFACE_MODEL_FILE", "best.onnx"),
        help="仓库中的 ONNX 文件名 (默认 best.onnx)",
    )
    parser.add_argument(
        "--output",
        default="models/pest_yolo.onnx",
        help="本地输出路径 (默认 models/pest_yolo.onnx)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    output_path = project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"模型文件已存在: {output_path}")
        print("如需重新下载, 请先删除该文件.")
        return

    if not args.repo:
        print("=" * 60)
        print("请指定 HuggingFace 模型仓库 ID:")
        print()
        print("  方法 1: 命令行参数")
        print("    python scripts/download_pest_model.py --repo your-username/yolov8-pest-detection")
        print()
        print("  方法 2: 环境变量")
        print("    export HUGGINGFACE_MODEL_REPO=your-username/yolov8-pest-detection")
        print("    python scripts/download_pest_model.py")
        print()
        print("推荐的 HuggingFace 搜索关键词:")
        print("  - yolov8 plant disease detection onnx")
        print("  - crop pest detection yolo onnx")
        print("  - agricultural disease classification onnx")
        print("=" * 60)
        sys.exit(1)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("需要安装 huggingface_hub:")
        print("  pip install huggingface_hub")
        sys.exit(1)

    print(f"正在从 HuggingFace 下载模型...")
    print(f"  仓库: {args.repo}")
    print(f"  文件: {args.filename}")
    print(f"  输出: {output_path}")
    print()

    try:
        downloaded = hf_hub_download(
            repo_id=args.repo,
            filename=args.filename,
            local_dir=str(output_path.parent),
        )
        # 如果下载的文件名不是目标名, 重命名
        downloaded_path = Path(downloaded)
        if downloaded_path != output_path:
            downloaded_path.rename(output_path)

        print(f"✅ 模型下载成功: {output_path}")
        print(f"   文件大小: {output_path.stat().st_size / 1024 / 1024:.1f} MB")

    except Exception as e:
        print(f"❌ 下载失败: {e}")
        print()
        print("可能的原因:")
        print("  1. 仓库 ID 不正确")
        print("  2. 文件名不正确 (使用 --filename 指定)")
        print("  3. 网络问题 (可尝试设置 HF_ENDPOINT)")
        print("  4. 需要登录: huggingface-cli login")
        sys.exit(1)


if __name__ == "__main__":
    main()
