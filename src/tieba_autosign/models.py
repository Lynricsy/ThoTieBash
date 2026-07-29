"""签到相关数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SignStatus(str, Enum):
    """单个贴吧的签到结果。"""

    SUCCESS = "success"
    ALREADY = "already"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(slots=True, frozen=True)
class Forum:
    """关注的贴吧。"""

    fid: str
    name: str


@dataclass(slots=True)
class ForumSignResult:
    """单个贴吧签到结果。"""

    forum: Forum
    status: SignStatus
    message: str = ""
    rank: int | None = None
    bonus_point: int | None = None


@dataclass(slots=True)
class AccountSummary:
    """单个账号的签到汇总。"""

    index: int
    label: str
    forums: int = 0
    success: int = 0
    already: int = 0
    blocked: int = 0
    failed: int = 0
    skipped: bool = False
    error: str | None = None
    details: list[ForumSignResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        # 主动跳过视为成功（凭证仍保留，只是不跑）
        return self.skipped or (self.error is None and self.failed == 0)


@dataclass(slots=True)
class RunSummary:
    """整次运行汇总。"""

    accounts: list[AccountSummary] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.accounts) and all(item.ok for item in self.accounts)
