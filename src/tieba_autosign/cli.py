"""命令行入口。"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .runner import format_summary, load_bduss_list, run_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tieba-autosign",
        description="百度贴吧自动签到（HTTPS / 现代 Python）",
    )
    parser.add_argument(
        "--bduss",
        help="显式传入 BDUSS；多账号可用 # / 逗号 / 换行分隔。默认读取环境变量 BDUSS",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.8,
        help="同一账号内贴吧签到间隔秒数，默认 0.8",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别，默认 INFO",
    )
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    bduss_list = load_bduss_list(args.bduss)
    if not bduss_list:
        logging.error("未提供 BDUSS。请设置环境变量 BDUSS，或使用 --bduss 传入。")
        return 2

    summary = asyncio.run(run_all(bduss_list, sign_interval=args.interval))
    print(format_summary(summary))
    return 0 if summary.ok else 1


if __name__ == "__main__":
    sys.exit(main())
