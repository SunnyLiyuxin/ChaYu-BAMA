"""seed.py — 把 YAML seed 灌进 SQLite（阶段二接 DB 时启用）。

阶段一不使用 SQLite：seed 文件即数据源，由 app.data_loader 直接加载到内存。
本脚本作为阶段二的占位：接 SQLAlchemy models 后，运行 `python scripts/seed.py --reset`
即可把同样的 seed 灌进 tea.db，保证可复现。

用法（阶段二启用后）：
    python scripts/seed.py --reset
"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="把 YAML seed 灌进 SQLite（阶段二启用）")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="重建数据库后重新导入全部 seed 数据",
    )
    args = parser.parse_args()

    if not args.reset:
        parser.print_help()
        return

    # 阶段二实现：建表 → 读 backend/data/seeds/*.yaml → 写入 tea.db
    # 当前阶段一无需 DB，直接提示。
    print(
        "[seed.py] 阶段一不使用 SQLite。数据由 app.data_loader 从 "
        "backend/data/seeds/*.yaml 直接加载到内存。\n"
        "阶段二接 SQLAlchemy 后，本脚本将重建 tea.db 并导入全部 seed。"
    )


if __name__ == "__main__":
    main()
