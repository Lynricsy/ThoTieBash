"""贴吧签到 HTTPS 协议客户端。"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from .const import (
    CLIENT_MODEL,
    CLIENT_TYPE,
    CLIENT_VERSION,
    DEFAULT_PAGE_SIZE,
    DEFAULT_SIGN_INTERVAL,
    DEFAULT_TIMEOUT,
    ERROR_ALREADY_SIGNED,
    ERROR_FORUM_BLOCKED,
    ERROR_OK,
    LIKE_URL,
    LOGIN_URL,
    NET_TYPE,
    PHONE_IMEI,
    SIGN_URL,
    TBS_URL,
)
from .crypto import sign_payload
from .models import Forum, ForumSignResult, SignStatus

logger = logging.getLogger(__name__)


class TiebaAuthError(RuntimeError):
    """BDUSS 无效或登录态失效。"""


class TiebaAPIError(RuntimeError):
    """贴吧接口返回业务错误。"""


class TiebaClient:
    """基于 httpx 的异步贴吧签到客户端。"""

    def __init__(
        self,
        bduss: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        sign_interval: float = DEFAULT_SIGN_INTERVAL,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not bduss or not bduss.strip():
            raise ValueError("BDUSS 不能为空")
        self.bduss: str = bduss.strip()
        self.sign_interval: float = max(sign_interval, 0.0)
        self._owns_client: bool = client is None
        self._client: httpx.AsyncClient = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": (
                    f"Mozilla/5.0 (Linux; Android 13; {CLIENT_MODEL}) "
                    f"tieba/{CLIENT_VERSION}"
                ),
                "Accept-Encoding": "gzip",
            },
            follow_redirects=True,
        )

    async def __aenter__(self) -> TiebaClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_tbs(self) -> str:
        """获取 tbs，并校验登录态。"""
        response = await self._request(
            "GET",
            TBS_URL,
            headers={"Cookie": f"BDUSS={self.bduss}"},
        )
        if int(response.get("is_login", 0)) != 1:
            # 网页 tbs 判定失败时，回退客户端登录接口
            return await self._login_for_tbs()
        tbs = str(response.get("tbs") or "").strip()
        if not tbs:
            raise TiebaAuthError("tbs 为空，登录态可能失效")
        return tbs

    async def _login_for_tbs(self) -> str:
        payload = sign_payload(
            {
                "_client_version": CLIENT_VERSION,
                "bdusstoken": self.bduss,
            }
        )
        response = await self._request("POST", LOGIN_URL, data=payload)
        code = str(response.get("error_code", ""))
        if code not in {"", ERROR_OK}:
            raise TiebaAuthError(
                f"登录失败: {response.get('error_msg', 'unknown')} ({code})"
            )
        tbs = str(response.get("anti", {}).get("tbs") or "").strip()
        if not tbs:
            raise TiebaAuthError("客户端登录成功但未返回 tbs")
        return tbs

    async def list_favorite_forums(self) -> list[Forum]:
        """分页获取当前账号关注的贴吧。"""
        forums: list[Forum] = []
        page_no = 1
        while True:
            payload = sign_payload(
                {
                    "BDUSS": self.bduss,
                    "_client_type": CLIENT_TYPE,
                    "_client_version": CLIENT_VERSION,
                    "_phone_imei": PHONE_IMEI,
                    "from": "tieba_autosign",
                    "page_no": str(page_no),
                    "page_size": str(DEFAULT_PAGE_SIZE),
                    "model": CLIENT_MODEL,
                    "net_type": NET_TYPE,
                    "timestamp": str(int(time.time())),
                    "vcode_tag": "11",
                }
            )
            response = await self._request("POST", LIKE_URL, data=payload)
            code = str(response.get("error_code", ERROR_OK))
            if code not in {"", ERROR_OK}:
                raise TiebaAPIError(
                    f"获取关注贴吧失败: {response.get('error_msg', 'unknown')} ({code})"
                )

            forums.extend(self._extract_forums(response.get("forum_list")))
            if str(response.get("has_more", "0")) != "1":
                break
            page_no += 1
            await asyncio.sleep(0.3)

        # 按 fid 去重，保持首次出现顺序
        deduped: dict[str, Forum] = {}
        for forum in forums:
            deduped.setdefault(forum.fid, forum)
        return list(deduped.values())

    async def sign_forum(self, forum: Forum, tbs: str) -> ForumSignResult:
        """对单个贴吧执行客户端签到。"""
        payload = sign_payload(
            {
                "BDUSS": self.bduss,
                "_client_type": CLIENT_TYPE,
                "_client_version": CLIENT_VERSION,
                "_phone_imei": PHONE_IMEI,
                "model": CLIENT_MODEL,
                "net_type": NET_TYPE,
                "fid": forum.fid,
                "kw": forum.name,
                "tbs": tbs,
                "timestamp": str(int(time.time())),
            }
        )
        try:
            response = await self._request("POST", SIGN_URL, data=payload)
        except Exception as exc:  # noqa: BLE001 - 汇总为失败结果
            return ForumSignResult(
                forum=forum,
                status=SignStatus.FAILED,
                message=f"请求异常: {exc}",
            )

        code = str(response.get("error_code", ""))
        message = str(response.get("error_msg") or "")
        user_info = response.get("user_info") or {}

        if code in {"", ERROR_OK}:
            rank = self._as_optional_int(user_info.get("user_sign_rank"))
            bonus = self._as_optional_int(user_info.get("sign_bonus_point"))
            return ForumSignResult(
                forum=forum,
                status=SignStatus.SUCCESS,
                message=message or "签到成功",
                rank=rank,
                bonus_point=bonus,
            )
        if code == ERROR_ALREADY_SIGNED:
            return ForumSignResult(
                forum=forum,
                status=SignStatus.ALREADY,
                message=message or "今日已签到",
            )
        if code == ERROR_FORUM_BLOCKED:
            return ForumSignResult(
                forum=forum,
                status=SignStatus.BLOCKED,
                message=message or "贴吧已被屏蔽",
            )
        return ForumSignResult(
            forum=forum,
            status=SignStatus.FAILED,
            message=message or f"签到失败 ({code})",
        )

    async def sign_all(self, forums: list[Forum], tbs: str) -> list[ForumSignResult]:
        """顺序签到，控制请求间隔，降低风控风险。"""
        results: list[ForumSignResult] = []
        for index, forum in enumerate(forums):
            result = await self.sign_forum(forum, tbs)
            results.append(result)
            logger.info(
                "[%s/%s] %s -> %s%s",
                index + 1,
                len(forums),
                forum.name,
                result.status.value,
                f" ({result.message})" if result.message else "",
            )
            if index + 1 < len(forums) and self.sign_interval > 0:
                await asyncio.sleep(self.sign_interval)
        return results

    async def _request(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        retries: int = 3,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                response = await self._client.request(
                    method,
                    url,
                    data=data,
                    headers=headers,
                )
                response.raise_for_status()
                if not response.content:
                    raise TiebaAPIError(f"空响应: {url}")
                payload = response.json()
                if not isinstance(payload, dict):
                    raise TiebaAPIError(f"响应不是 JSON 对象: {url}")
                return payload
            except (httpx.HTTPError, ValueError, TiebaAPIError) as exc:
                last_error = exc
                if attempt >= retries:
                    break
                delay = 0.6 * (2 ** (attempt - 1))
                logger.warning(
                    "请求失败，准备重试 (%s/%s): %s | %s",
                    attempt,
                    retries,
                    url,
                    exc,
                )
                await asyncio.sleep(delay)
        assert last_error is not None
        raise TiebaAPIError(f"请求失败: {url} | {last_error}") from last_error

    @staticmethod
    def _extract_forums(forum_list: Any) -> list[Forum]:
        if not forum_list:
            return []

        raw_items: list[Any] = []
        if isinstance(forum_list, list):
            raw_items = forum_list
        elif isinstance(forum_list, dict):
            for key in ("non-gconforum", "gconforum"):
                value = forum_list.get(key)
                if isinstance(value, list):
                    raw_items.extend(value)
                elif isinstance(value, dict):
                    raw_items.append(value)

        forums: list[Forum] = []
        for item in TiebaClient._flatten(raw_items):
            if not isinstance(item, dict):
                continue
            fid = str(item.get("id") or item.get("forum_id") or "").strip()
            name = str(item.get("name") or item.get("forum_name") or "").strip()
            if fid and name:
                forums.append(Forum(fid=fid, name=name))
        return forums

    @staticmethod
    def _flatten(items: list[Any]) -> list[Any]:
        result: list[Any] = []
        for item in items:
            if isinstance(item, list):
                result.extend(TiebaClient._flatten(item))
            else:
                result.append(item)
        return result

    @staticmethod
    def _as_optional_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
