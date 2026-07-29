"""核心逻辑单测（不访问真实贴吧网络）。"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest

from tieba_autosign.cli import resolve_bduss_source
from tieba_autosign.client import (
    InsecureRedirectError,
    TiebaAPIError,
    TiebaClient,
    is_https_to_http_redirect,
)
from tieba_autosign.const import APP_SALT, LOGIN_URL
from tieba_autosign.crypto import sign_payload
from tieba_autosign.models import AccountSummary, Forum, ForumSignResult, RunSummary, SignStatus
from tieba_autosign.runner import format_summary, load_bduss_list, mask_bduss


def test_sign_payload_matches_client_algorithm() -> None:
    data = {
        "BDUSS": "demo",
        "kw": "linux",
        "timestamp": "1710000000",
    }
    signed = sign_payload(data)
    raw = "".join(f"{k}={data[k]}" for k in sorted(data))
    expected = hashlib.md5(raw.encode("utf-8") + APP_SALT).hexdigest()
    assert signed["sign"] == expected
    assert signed["kw"] == "linux"


def test_load_bduss_list_supports_multiple_separators() -> None:
    raw = "aaa#bbb, ccc\nddd\n\n"
    assert load_bduss_list(raw) == ["aaa", "bbb", "ccc", "ddd"]


def test_resolve_bduss_source_from_file(tmp_path: Path) -> None:
    path = tmp_path / "bduss.txt"
    path.write_text("aaa#bbb\n", encoding="utf-8")
    assert resolve_bduss_source(str(path)) == ["aaa", "bbb"]


def test_mask_bduss() -> None:
    assert mask_bduss("short") == "***"
    assert mask_bduss("1234567890abcdef") == "1234...cdef"


def test_extract_forums_handles_nested_shapes() -> None:
    forums = TiebaClient._extract_forums(
        {
            "non-gconforum": [
                {"id": "1", "name": "linux"},
                [{"id": "2", "name": "python"}],
            ],
            "gconforum": {"id": "3", "name": "rust"},
        }
    )
    assert [(f.fid, f.name) for f in forums] == [
        ("1", "linux"),
        ("2", "python"),
        ("3", "rust"),
    ]


def test_format_summary_reports_failures() -> None:
    summary = RunSummary(
        accounts=[
            AccountSummary(
                index=1,
                label="abcd...wxyz",
                forums=2,
                success=1,
                failed=1,
                details=[
                    ForumSignResult(
                        forum=Forum("1", "linux"),
                        status=SignStatus.SUCCESS,
                        message="ok",
                    ),
                    ForumSignResult(
                        forum=Forum("2", "python"),
                        status=SignStatus.FAILED,
                        message="boom",
                    ),
                ],
            )
        ]
    )
    text = format_summary(summary)
    assert "python" in text
    assert "存在失败" in text
    assert not summary.ok


@pytest.mark.asyncio
async def test_missing_bduss_rejected() -> None:
    with pytest.raises(ValueError):
        TiebaClient("   ")


def test_detect_https_to_http_redirect() -> None:
    assert is_https_to_http_redirect(
        "https://tieba.baidu.com/dc/common/tbs",
        "http://tieba.baidu.com/dc/common/tbs?red_tag=1",
    )
    assert not is_https_to_http_redirect(
        "https://tiebac.baidu.com/c/s/login",
        "https://tiebac.baidu.com/c/s/login",
    )


@pytest.mark.asyncio
async def test_request_rejects_https_to_http_redirect() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            301,
            headers={"Location": "http://tieba.baidu.com/dc/common/tbs"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as session:
        client = TiebaClient("demo-bduss-token", client=session)
        with pytest.raises(InsecureRedirectError):
            await client._request("GET", "https://tieba.baidu.com/dc/common/tbs")


@pytest.mark.asyncio
async def test_request_rejects_plain_http_url() -> None:
    async with httpx.AsyncClient(follow_redirects=False) as session:
        client = TiebaClient("demo-bduss-token", client=session)
        with pytest.raises(TiebaAPIError, match="拒绝非 HTTPS"):
            await client._request("GET", "http://example.com")


@pytest.mark.asyncio
async def test_get_tbs_uses_https_login() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert str(request.url).startswith("https://")
        return httpx.Response(
            200,
            json={"error_code": "0", "anti": {"tbs": "tbsofficial"}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as session:
        client = TiebaClient("demo-bduss-token", client=session)
        tbs = await client.get_tbs()

    assert tbs == "tbsofficial"
    assert seen == [LOGIN_URL]
