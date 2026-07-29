# TiebaAutoSign

百度贴吧自动签到工具。

从旧项目 [ThoTieBash](https://github.com/Lynricsy/ThoTieBash) 现代化翻修：

- **运行时**：Python **3.14**
- **HTTP**：`httpx`（全站 **HTTPS**）
- **协议**：较新客户端版本字段 + 结构化结果汇总
- **部署**：GitHub Actions 定时签到

> 目标只有一个：稳定签到、凭证不裸奔、失败看得见。

## 功能

- 多账号：`BDUSS` 支持 `#` / 逗号 / 换行分隔
- 自动拉取关注贴吧并客户端签到
- 结果分类：成功 / 已签 / 屏蔽 / 失败
- 失败时进程以非 0 退出（CI 会红）
- 日志对 `BDUSS` 脱敏

## 快速开始

### 本地

```bash
# 需要 uv（或自行创建 venv 后 pip install -e .）
uv sync

# 推荐：环境变量（不会进入 argv / shell 历史里的明文参数）
export BDUSS='你的BDUSS'
uv run tieba-autosign

# 多账号同样走环境变量，使用 # / 逗号 / 换行分隔
export BDUSS='账号1的BDUSS#账号2的BDUSS'
uv run tieba-autosign --interval 1.0
```

也可以从文件或 stdin 读取（文件权限请设为仅本人可读）：

```bash
chmod 600 bduss.txt
uv run tieba-autosign --bduss-file bduss.txt

# 或管道（注意控制 shell 历史，例如 set +o history）
printenv BDUSS | uv run tieba-autosign --bduss-file -
```

> 安全约定：**不要**使用命令行明文参数传入 BDUSS。
> 凭证只应来自环境变量、Actions Secret、权限受限的本地文件或 stdin。

### 获取 BDUSS

1. 浏览器登录 [贴吧](https://tieba.baidu.com)
2. 打开开发者工具 → Application / 存储 → Cookies
3. 复制 `BDUSS` 的值（不要提交到仓库）

## GitHub Actions

1. Fork / 推送本仓库
2. `Settings` → `Secrets and variables` → `Actions` → 新建 secret：
   - 名称：`BDUSS`
   - 值：一个或多个 BDUSS（多账号用 `#` 连接）
3. 打开 Actions，手动跑一次 `Tieba Auto Sign`
4. 默认每天 UTC `16:05` / `22:05` 执行（约北京时间 00:05 / 06:05）

可选 secret：

| 名称 | 说明 |
|------|------|
| `BDUSS` | 必填，账号凭证 |
| `SIGN_INTERVAL` | 可选，贴吧之间间隔秒数，默认 `0.8` |

## 设计说明

| 层 | 选择 | 原因 |
|----|------|------|
| 运行时 | Python 3.14 | 主人要求最新稳定栈；语法与类型注解现代 |
| HTTP | httpx | 官方维护活跃，async 一等公民 |
| 协议 | 自研精简客户端 | 只做签到，不引入重量级吧务库 |
| 部署 | GitHub Actions | 自用零成本定时，足够 |

安全底线：

- 接口全部 `https://`
- `BDUSS` 只进环境变量 / Actions Secret / 本地文件 / stdin
- **禁止**命令行明文 `--bduss`（避免 shell 历史与进程参数泄露）
- 日志输出脱敏

## 退出码

| 码 | 含义 |
|----|------|
| `0` | 全部账号处理成功（允许「今日已签」） |
| `1` | 存在失败 / 认证错误 / 业务失败 |
| `2` | 未提供 BDUSS 等参数错误 |

## 开发

```bash
uv sync --group dev
uv run pytest
uv run python -m compileall src
```

## 许可

Apache-2.0
