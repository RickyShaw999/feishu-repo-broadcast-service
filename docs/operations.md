# 运维

## 运行时模型

此服务在 v1 中是单租户：一个部署接收一个仓库的 Codeup 或 GitLab push Webhook，并发送到一个飞书群机器人。

服务将持久状态存储在 SQLite 中：

- 按去重键记录的入站接收记录
- outbox 行
- 投递尝试
- 重试调度

Outbox 状态包括 `pending`、`in_progress`、`retry_scheduled`、`delivered` 和 `failed_terminal`。

## 本地 Dry Run

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
python scripts/dev_send_fixture.py codeup tests/fixtures/codeup_push.json --base-url http://127.0.0.1:8088 --token "$(grep '^CODEUP_SECRET_TOKEN=' .env | cut -d= -f2-)"
python scripts/dev_send_fixture.py gitlab tests/fixtures/gitlab_push.json --base-url http://127.0.0.1:8088 --token "$(grep '^GITLAB_SECRET_TOKEN=' .env | cut -d= -f2-)"
docker compose logs --no-color --tail=200
```

Dry-run 模式会将飞书载荷记录到 `delivery_attempts.response_body`，不会发起网络调用。

## 生产环境 Compose Secrets

1. 创建 `secrets/README.md` 中记录的密钥文件。
2. 将 `compose.override.example.yaml` 复制为 `compose.override.yaml`。
3. 在 `.env` 中设置 `PUBLIC_HOST` 和 `HTTP_PORT`。
4. 保持 `HTTPS_PORT=443` 对外暴露，以便 Caddy 为真实公网域名提供自动 HTTPS。
5. 运行 `docker compose up -d --build`。

## 健康探针

- `/health` 证明进程存活。
- `/ready` 证明 SQLite 可以打开。

## Webhook 路径

- Codeup: `/webhooks/codeup`
- GitLab: `/webhooks/gitlab`

## 失败处理

可重试失败包括网络超时、传输失败、HTTP 429 和 HTTP 5xx。终止性失败包括缺少 live 飞书 URL、载荷格式错误、提供方 token 无效，以及除限流外的永久性 HTTP 4xx 响应。

启动时，过期的 `in_progress` 行会返回重试处理流程。已标记为 `delivered` 的行永远不会重新发送。
