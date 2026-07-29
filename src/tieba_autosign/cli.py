"""命令行入口。"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .runner import format_summary, load_bduss_list, parse_skip_accounts, run_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tieba-autosign",
        description="private personal utility",
    )
    parser.add_argument(
        "--bduss-file",
        metavar="PATH",
        help=(
            "从文件读取 BDUSS（支持多账号分隔）。"
            "使用 '-' 表示从标准输入读取。"
            "默认读取环境变量 BDUSS。"
        ),
    )
    parser.add_argument(
        "--skip-accounts",
        default=None,
        help=(
            "跳过的账号序号（1-based），例如 2 或 2,3。"
            "默认读取环境变量 SKIP_ACCOUNTS；未设置则不跳过。"
            "被跳过账号的凭证仍保留。"
        ),
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.8,
        help="同一账号内请求间隔秒数，默认 0.8",
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


def resolve_bduss_source(bduss_file: str | None) -> list[str]:
    """仅允许环境变量 / 文件 / stdin，禁止命令行明文凭证。"""
    if bduss_file is None:
        return load_bduss_list()

    if bduss_file == "-":
        raw = sys.stdin.read()
        return load_bduss_list(raw)

    path = Path(bduss_file)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logging.error("无法读取凭证文件 %s: %s", path, exc)
        return []
    return load_bduss_list(raw)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log_level = str(args.log_level)
    interval = float(args.interval)
    bduss_file = args.bduss_file
    skip_raw = args.skip_accounts
    configure_logging(log_level)

    bduss_list = resolve_bduss_source(
        None if bduss_file is None else str(bduss_file)
    )
    if not bduss_list:
        logging.error(
            "未提供凭证。请设置环境变量 BDUSS，"
            "或使用 --bduss-file / --bduss-file -（stdin）。"
        )
        return 2

    # 应用默认：不跳过；仅当 CLI/环境显式配置时才跳过
    skip_accounts = parse_skip_accounts(
        None if skip_raw is None else str(skip_raw)
    )
    if skip_accounts:
        logging.info("跳过账号序号: %s", sorted(skip_accounts))

    summary = asyncio.run(
        run_all(
            bduss_list,
            sign_interval=interval,
            skip_accounts=skip_accounts,
        )
    )
    print(format_summary(summary))
    return 0 if summary.ok else 1


if __name__ == "__main__":
    sys.exit(main())
