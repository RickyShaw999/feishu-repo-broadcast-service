# 飞书仓库广播服务

`feishu-repo-broadcast-service` 是一个可用于生产环境的单租户 Webhook 接收服务。它接收一个代码仓库的 push 事件，将提交信息整理成飞书消息，然后发送到一个飞书群机器人。

这个服务的设计目标很明确：一个服务实例只服务一个仓库和一个飞书机器人。这样部署、排查、密钥管理和重复消息控制都更简单，也能避免多个仓库共用同一个实例时带来的权限和审计复杂度。

## 功能范围

v1 支持：

- Codeup push Webhook
- GitLab push Webhook
- 每个仓库与飞书机器人对应一个服务实例
- Docker Compose 部署
- 使用 Docker Compose secrets 管理生产环境配置值
- SQLite outbox、去重、重试状态与重启恢复
- 在任何真实飞书调用前使用 dry-run 模式

不支持，也暂不计划在 v1 中支持：

- PR/MR/comment/review 事件
- 在一个实例中支持多个仓库或多个飞书机器人
- Codeup 和 GitLab 之外的提供方
- UI/管理控制台
- 复杂权限或审计系统

## 工作方式

服务收到 Codeup 或 GitLab 的 push Webhook 后，会先校验提供方传来的 secret token。校验通过后，服务会把事件转换成飞书消息，并通过 SQLite 记录处理状态。

SQLite 用来保存 outbox、去重信息、投递尝试、重试状态和重启恢复所需的数据。这样即使服务中途重启，也可以继续处理未完成的投递；已经标记为成功投递的事件不会再次发送。

默认部署运行在 `dry_run` 模式。这个模式会生成飞书消息载荷，把它写入 SQLite 并打印投递状态日志，但不会真正调用飞书接口。只有显式切换到 `DELIVERY_MODE=live` 后，服务才会发送真实飞书消息。

## 快速开始：本地 Dry Run

下面的命令会创建本地 `.env`，生成临时的 Codeup/GitLab token，把服务端口改到本机测试用端口，然后启动 Docker Compose：

```bash
cp .env.example .env
python - <<'PY'
import secrets
from pathlib import Path
path = Path(".env")
text = path.read_text()
text = text.replace("CODEUP_SECRET_TOKEN=", f"CODEUP_SECRET_TOKEN={secrets.token_urlsafe(32)}")
text = text.replace("GITLAB_SECRET_TOKEN=", f"GITLAB_SECRET_TOKEN={secrets.token_urlsafe(32)}")
text = text.replace("PUBLIC_HOST=repo-broadcast.example.com", "PUBLIC_HOST=:80")
text = text.replace("HTTP_PORT=80", "HTTP_PORT=8088")
text = text.replace("HTTPS_PORT=443", "HTTPS_PORT=8443")
path.write_text(text)
PY
docker compose up -d --build
curl -fsS http://127.0.0.1:8088/health
python scripts/dev_send_fixture.py codeup tests/fixtures/codeup_push.json --base-url http://127.0.0.1:8088 --token "$(grep '^CODEUP_SECRET_TOKEN=' .env | cut -d= -f2-)"
python scripts/dev_send_fixture.py gitlab tests/fixtures/gitlab_push.json --base-url http://127.0.0.1:8088 --token "$(grep '^GITLAB_SECRET_TOKEN=' .env | cut -d= -f2-)"
docker compose logs --no-color --tail=200
```

执行完成后，重点确认三件事：

1. `/health` 返回成功，说明进程已经启动。
2. 两个 fixture POST 都能被服务接收。
3. 日志中能看到投递状态；在默认 `dry_run` 模式下，服务不会调用飞书，只会把渲染后的飞书载荷存入 SQLite。

## Webhook 配置

一个服务实例只应该配置给一个仓库使用。仓库侧只开启 push 事件，不要把 PR、MR、评论或 review 事件发到此服务。

Codeup 配置：

- URL：`https://<host>/webhooks/codeup`
- 触发器：push 事件
- 密钥 token：存储在 `CODEUP_SECRET_TOKEN` 或 `secrets/codeup_secret_token.txt` 中的值

GitLab 配置：

- URL：`https://<host>/webhooks/gitlab`
- 触发器：push 事件
- 密钥 token：存储在 `GITLAB_SECRET_TOKEN` 或 `secrets/gitlab_secret_token.txt` 中的值

如果是本地 dry-run，可以先用 fixture 脚本模拟提供方请求；如果是生产部署，请先确认 `/health`、`/ready`、fixture POST、重复回放和日志都正常，再切换到 live 模式。

## 飞书消息结构

每条出站飞书消息包含两个部分：

1. `Technical Explanation Protocol`：操作人、动作、仓库、分支、版本范围、提交数量，以及简洁的提交详情。
2. `Original Event`：提供方、ref、before/after SHA，以及有界的原始载荷块。

这样设计是为了让群里的人能先读到清晰的提交摘要，同时在需要排查时也能看到原始事件的关键字段。

## 生产环境密钥

生产环境不要把密钥直接写入仓库。推荐使用 Docker Compose secrets，把运行时密钥放到本地文件中，再由 Compose 挂载进容器。

最小生产配置示例：

```bash
cp compose.override.example.yaml compose.override.yaml
mkdir -p secrets
printf '%s' '<codeup-token>' > secrets/codeup_secret_token.txt
printf '%s' '<gitlab-token>' > secrets/gitlab_secret_token.txt
printf '%s' '<feishu-webhook-url>' > secrets/feishu_webhook_url.txt
DELIVERY_MODE=live docker compose up -d --build
```

如果启用了飞书机器人签名，还需要创建：

```text
secrets/feishu_signing_secret.txt
```

然后取消 `compose.override.yaml` 中签名密钥相关行的注释。

不要提交 `secrets/*.txt` 下的文件。

## 配置项

| 名称 | 默认值 | 用途 |
| --- | --- | --- |
| `DELIVERY_MODE` | `dry_run` | 投递模式。默认只记录载荷与状态；仅在真实飞书投递时使用 `live`。 |
| `DATABASE_PATH` | Compose 中为 `/data/service.db` | SQLite 状态路径。 |
| `CODEUP_SECRET_TOKEN` / `_FILE` | 必填 | Codeup 请求校验 token。 |
| `GITLAB_SECRET_TOKEN` / `_FILE` | 必填 | GitLab 请求校验 token。 |
| `FEISHU_WEBHOOK_URL` / `_FILE` | 空 | `live` 投递必填。 |
| `FEISHU_SIGNING_SECRET` / `_FILE` | 空 | 可选的飞书自定义机器人签名密钥。 |
| `MAX_DELIVERY_ATTEMPTS` | `5` | 重试耗尽阈值。 |
| `LEASE_TIMEOUT_SECONDS` | `300` | 被中断的 `in_progress` 行的回收超时时间。 |
| `PUBLIC_HOST` | 必填 | Caddy 站点地址。自动 HTTPS 使用真实域名；`:80` 仅用于本地 dry-run。 |
| `HTTP_PORT` | `80` | 对外发布的 HTTP 端口。 |
| `HTTPS_PORT` | `443` | 用于生产环境 Caddy 自动 TLS 的对外发布 HTTPS 端口。 |

## 健康检查与验证

服务提供两个健康检查路径：

- `/health`：证明进程存活。
- `/ready`：证明 SQLite 可以打开。

建议上线前按这个顺序验证：

1. 本地或目标环境启动服务。
2. 请求 `/health`。
3. 请求 `/ready`。
4. 发送一次 fixture POST。
5. 重放同一个 fixture，确认返回 `duplicate`，并且不会产生第二次投递。
6. 查看 `docker compose logs --no-color --tail=200`，确认日志中的处理状态符合预期。
7. 确认 dry-run 全部通过后，再进入 live 模式。

## 手动 Live 测试

只有在 dry-run 路径已经通过后，才进行 live 测试。

测试前确认：

- 飞书机器人已添加到目标群聊。
- `secrets/feishu_webhook_url.txt` 包含完整的自定义机器人 Webhook URL。
- 如果启用了机器人签名，`secrets/feishu_signing_secret.txt` 包含签名密钥。
- 提供方密钥文件包含与 Codeup 或 GitLab 中配置一致的 token。

启用 live 模式：

```bash
cp compose.override.example.yaml compose.override.yaml
DELIVERY_MODE=live docker compose up -d --build
```

然后发送一个受控 fixture，或发送一次真实的提供方 push 事件。确认飞书群只收到一条消息，服务日志显示 `delivery.delivered`，并且回放同一个 fixture 返回 `duplicate`，不会发送第二条消息。

上线证据建议保留两部分：服务日志，以及人工确认飞书群收到消息的记录。

## 开发

本地开发和测试命令：

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
python -m compileall src tests
pytest -q
```

## Agent 安装提示词

为其他仓库安装此服务时，可将以下提示词提供给 agent：

```text
为此仓库配置 feishu-repo-broadcast-service。
要求：
- 将该服务作为独立的同级仓库或外部依赖保留，不要放入产品代码
- 根据当前 remote 选择 Codeup 或 GitLab 提供方
- 只为 push 事件配置一个 webhook 端点
- 使用 Docker Compose secrets 存放提供方 token 和飞书 webhook 值
- 从 DELIVERY_MODE=dry_run 开始
- 进入 live 模式前，验证 /health、/ready、一次 fixture POST、重复回放和日志
- 在我提供 webhook 密钥值并明确批准 live 测试前，不要发送真实飞书消息
```

## `pengleni` 试点

对于当前 `pengleni` 试点，请将此仓库独立保留在：

```text
/Users/rickyshaw/Documents/Codebase/feishu-repo-broadcast-service
```

将 Codeup 仓库 Webhook 指向已部署的 `/webhooks/codeup` URL，仅使用 push 事件，并保持 `pengleni` 业务代码不变。
