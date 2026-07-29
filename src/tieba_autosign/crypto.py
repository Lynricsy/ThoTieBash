"""贴吧客户端表单签名。"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from .const import APP_SALT


def sign_payload(data: Mapping[str, str | int]) -> dict[str, str]:
    """为表单参数附加客户端 sign 字段。"""
    payload = {str(k): str(v) for k, v in data.items()}
    raw = "".join(f"{key}={payload[key]}" for key in sorted(payload))
    digest = hashlib.md5(raw.encode("utf-8") + APP_SALT).hexdigest()
    payload["sign"] = digest
    return payload
