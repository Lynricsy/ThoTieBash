"""贴吧客户端协议常量。"""

from __future__ import annotations

# 对齐活跃客户端实现（aiotieba）的较新版本号
CLIENT_VERSION = "22.6.5.1"
CLIENT_TYPE = "2"
PHONE_IMEI = "000000000000000"
CLIENT_MODEL = "Pixel 6"
NET_TYPE = "1"

APP_BASE_HOST = "tiebac.baidu.com"
WEB_BASE_HOST = "tieba.baidu.com"

# 签名盐，贴吧客户端长期使用
APP_SALT = b"tiebaclient!!!"


LOGIN_URL = f"https://{APP_BASE_HOST}/c/s/login"
LIKE_URL = f"https://{APP_BASE_HOST}/c/f/forum/like"
SIGN_URL = f"https://{APP_BASE_HOST}/c/c/forum/sign"

# 常见签到错误码
ERROR_OK = "0"
ERROR_ALREADY_SIGNED = "160002"
ERROR_FORUM_BLOCKED = "340006"

DEFAULT_PAGE_SIZE = 200
DEFAULT_TIMEOUT = 15.0
DEFAULT_SIGN_INTERVAL = 0.8
