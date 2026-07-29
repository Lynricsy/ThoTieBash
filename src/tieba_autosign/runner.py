"""多账号签到编排。"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence

from .client import TiebaAuthError, TiebaClient
from .models import AccountSummary, RunSummary, SignStatus

logger = logging.getLogger(__name__)


def mask_bduss(bduss: str) -> str:
    """日志脱敏，只保留首尾少量字符。"""
    token = bduss.strip()
    if len(token) <= 10:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def load_bduss_list(raw: str | None = None) -> list[str]:
    """
    解析多账号 BDUSS。

    - raw 为 None：读取环境变量 BDUSS
    - raw 为字符串：解析该文本（供文件 / stdin 使用）

    支持分隔符：`#`、换行、英文逗号。
    不要把凭证放进命令行参数。
    """
    text = raw if raw is not None else os.environ.get("BDUSS", "")
    if not text or not text.strip():
        return []

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts: list[str] = []
    for chunk in normalized.split("\n"):
        for item in chunk.replace(",", "#").split("#"):
            value = item.strip()
            if value:
                parts.append(value)
    return parts


async def run_account(index: int, bduss: str, *, sign_interval: float) -> AccountSummary:
    """执行单个账号签到。"""
    label = mask_bduss(bduss)
    summary = AccountSummary(index=index, label=label)

    try:
        async with TiebaClient(bduss, sign_interval=sign_interval) as client:
            tbs = await client.get_tbs()
            forums = await client.list_favorite_forums()
            summary.forums = len(forums)
            if not forums:
                logger.warning("账号 %s 未获取到关注贴吧", label)
                return summary

            details = await client.sign_all(forums, tbs)
            summary.details = details
            for item in details:
                if item.status is SignStatus.SUCCESS:
                    summary.success += 1
                elif item.status is SignStatus.ALREADY:
                    summary.already += 1
                elif item.status is SignStatus.BLOCKED:
                    summary.blocked += 1
                else:
                    summary.failed += 1
    except TiebaAuthError as exc:
        summary.error = f"认证失败: {exc}"
        logger.error("账号 %s 认证失败: %s", label, exc)
    except Exception as exc:  # noqa: BLE001 - 顶层汇总
        summary.error = f"执行异常: {exc}"
        logger.exception("账号 %s 执行异常", label)

    return summary


async def run_all(
    bduss_list: Sequence[str],
    *,
    sign_interval: float = 0.8,
) -> RunSummary:
    """串行处理多账号，避免同出口 IP 并发过高。"""
    summary = RunSummary()
    total = len(bduss_list)
    for index, bduss in enumerate(bduss_list, start=1):
        logger.info("开始处理账号 %s/%s (%s)", index, total, mask_bduss(bduss))
        account = await run_account(index, bduss, sign_interval=sign_interval)
        summary.accounts.append(account)
        if account.error:
            logger.error(
                "账号 %s/%s 结束: 失败 - %s",
                index,
                total,
                account.error,
            )
        else:
            logger.info(
                "账号 %s/%s 结束: 总数=%s 成功=%s 已签=%s 屏蔽=%s 失败=%s",
                index,
                total,
                account.forums,
                account.success,
                account.already,
                account.blocked,
                account.failed,
            )
    return summary


def format_summary(summary: RunSummary) -> str:
    """生成可读的运行摘要。"""
    if not summary.accounts:
        return "没有可处理的账号。"

    lines = ["===== 贴吧签到汇总 ====="]
    for account in summary.accounts:
        head = f"[账号{account.index}] {account.label}"
        if account.error:
            lines.append(f"{head}: ❌ {account.error}")
            continue
        lines.append(
            f"{head}: 关注{account.forums} | "
            f"✅{account.success} | 💤{account.already} | "
            f"🚫{account.blocked} | ❌{account.failed}"
        )
        failures = [
            item
            for item in account.details
            if item.status is SignStatus.FAILED
        ]
        for item in failures[:20]:
            lines.append(f"  - {item.forum.name}: {item.message}")
        if len(failures) > 20:
            lines.append(f"  - ... 另有 {len(failures) - 20} 个失败项")
    lines.append("========================")
    lines.append("结果: " + ("全部成功" if summary.ok else "存在失败"))
    return "\n".join(lines)
