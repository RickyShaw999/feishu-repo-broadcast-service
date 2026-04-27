# 飞书仓库广播服务

这个仓库提供一个小型服务：当 Codeup 或 GitLab 仓库发生 push 时，服务接收仓库发来的 Webhook，把提交信息整理成飞书消息，再发到一个飞书群机器人。

先记住三个原则：

- 一个服务实例只对应一个代码仓库。
- 一个服务实例只对应一个飞书群机器人。
- 先跑 `dry_run`，确认服务能收到事件、能生成消息、能去重，但不真的发飞书；确认无误后再切到 `live`。

## 先回答：本地启动时，Codeup 新建 Webhook 应该填什么

如果你现在只是“在自己电脑本地启动了这个 codebase”，一般先不要去 Codeup 新建 Webhook。

原因很简单：Codeup 是云端服务，它访问不到你电脑里的 `127.0.0.1:8088`。所以如果你在 Codeup Webhook URL 里填：

```text
http://127.0.0.1:8088/webhooks/codeup
```

Codeup 会访问它自己的 `127.0.0.1`，不是你的电脑，肯定打不到你的本地服务。

本地阶段推荐这样做：

1. 本地启动服务。
2. 用仓库里的 fixture 脚本模拟一次 Codeup 请求。
3. 看日志确认服务能收到事件、能生成消息、能去重。
4. 等部署到公网服务器，或者你有公网隧道后，再去 Codeup 后台配置真实 Webhook。

如果你已经有公网服务器，Codeup 新建 Webhook 填：

| Codeup 表单项 | 应该填写 |
| --- | --- |
| URL / Webhook URL / 请求地址 | `https://<你的域名>/webhooks/codeup` |
| 触发事件 | 只选 push 事件 |
| Secret Token / Token / 密钥 | 和服务端配置的一样。生产环境通常是 `secrets/codeup_secret_token.txt` 里的内容 |
| SSL 校验 | 如果使用正常 HTTPS 域名，保持开启 |

如果你只是本地启动，但通过 ngrok、cloudflared tunnel、frp 等工具暴露了一个公网 HTTPS 地址，Codeup 新建 Webhook 可以填：

| Codeup 表单项 | 应该填写 |
| --- | --- |
| URL / Webhook URL / 请求地址 | `https://<你的公网隧道域名>/webhooks/codeup` |
| 触发事件 | 只选 push 事件 |
| Secret Token / Token / 密钥 | `.env` 里的 `CODEUP_SECRET_TOKEN` |
| SSL 校验 | 如果隧道是正常 HTTPS，保持开启 |

查看本地 `.env` 里的 Codeup token：

```bash
grep '^CODEUP_SECRET_TOKEN=' .env | cut -d= -f2-
```

Codeup Webhook 的 secret token 必须和服务端的 token 一模一样。比如服务端 token 是 `abc123`，Codeup 后台也必须填 `abc123`。两边不一致，服务会返回 `401 invalid Codeup secret token`。

## 这个服务最终怎么工作

完整流程是：

1. 有人向 Codeup 或 GitLab 仓库 push 代码。
2. 仓库平台向本服务发送 Webhook 请求。
3. 本服务检查请求是不是 push 事件。
4. 本服务检查请求里的 secret token 是否正确。
5. 校验通过后，本服务把 push 事件整理成飞书消息。
6. 服务把处理状态写入 SQLite，避免同一个事件重复发送。
7. `dry_run` 模式只记录消息，不发飞书。
8. `live` 模式会真正调用飞书机器人 Webhook，把消息发到群里。

Codeup 请求进入服务时，服务实际检查的是：

- 请求路径：`/webhooks/codeup`
- 事件头：`Codeup-Event: Push Hook`
- token 头：`X-Codeup-Token: <你配置的 token>`

这些请求头通常由 Codeup 平台自动发送。你在 Codeup 后台主要需要填 URL、push 事件、secret token。

## 功能范围

v1 支持：

- Codeup push Webhook
- GitLab push Webhook
- 每个仓库与飞书机器人对应一个服务实例
- Docker Compose 部署
- 使用 Docker Compose secrets 管理生产环境配置值
- SQLite outbox、去重、重试状态与重启恢复
- 在任何真实飞书调用前使用 dry-run 模式

v1 不支持：

- PR/MR/comment/review 事件
- 在一个实例中支持多个仓库或多个飞书机器人
- Codeup 和 GitLab 之外的提供方
- UI/管理控制台
- 复杂权限或审计系统

## 路线 A：只在本地测试，不接 Codeup 后台

这条路线适合你现在的状态：代码在本地，服务也在本地启动，还没有公网域名。

### A1. 准备 `.env`

复制环境变量示例文件：

```bash
cp .env.example .env
```

生成本地测试用 token，并把端口改成本机测试端口：

```bash
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
```

这一步会把 token 写进 `.env`，例如：

```dotenv
CODEUP_SECRET_TOKEN=<随机生成的一长串>
GITLAB_SECRET_TOKEN=<随机生成的一长串>
DELIVERY_MODE=dry_run
```

本地测试时不需要创建 `secrets/codeup_secret_token.txt`。

### A2. 启动服务

```bash
docker compose up -d --build
```

查看容器是否起来：

```bash
docker compose ps
```

### A3. 检查服务健康状态

检查进程是否活着：

```bash
curl -fsS http://127.0.0.1:8088/health
```

检查 SQLite 是否能打开：

```bash
curl -fsS http://127.0.0.1:8088/ready
```

这两个命令没有报错，就说明服务基础状态正常。

### A4. 用 fixture 脚本模拟 Codeup 请求

fixture 脚本的意思是：不用真的去 Codeup 后台配置 Webhook，而是在你电脑上伪造一条 Codeup push 请求，直接 POST 给本地服务。

发送 Codeup 测试事件：

```bash
python scripts/dev_send_fixture.py codeup tests/fixtures/codeup_push.json --base-url http://127.0.0.1:8088 --token "$(grep '^CODEUP_SECRET_TOKEN=' .env | cut -d= -f2-)"
```

这个命令做了几件事：

1. 读取 `tests/fixtures/codeup_push.json` 里的测试 push 事件。
2. 从 `.env` 读取 `CODEUP_SECRET_TOKEN`。
3. 向 `http://127.0.0.1:8088/webhooks/codeup` 发送 POST 请求。
4. 带上 `Codeup-Event: Push Hook` 和 `X-Codeup-Token: <token>`。

如果成功，你会看到类似：

```text
200
{"status":"accepted", ...}
```

### A5. 看日志

```bash
docker compose logs --no-color --tail=200
```

你要确认：

- 日志里有 `webhook.accepted provider=codeup`。
- 因为现在是 `DELIVERY_MODE=dry_run`，服务不会真的调用飞书。
- 服务会把渲染后的飞书消息载荷和投递状态写进 SQLite。

### A6. 测试重复事件不会重复处理

再执行一次同样的 Codeup fixture 命令：

```bash
python scripts/dev_send_fixture.py codeup tests/fixtures/codeup_push.json --base-url http://127.0.0.1:8088 --token "$(grep '^CODEUP_SECRET_TOKEN=' .env | cut -d= -f2-)"
```

第二次应该看到：

```text
"status":"duplicate"
```

这表示服务识别出这是同一个事件，不会重复发送。

### A7. 本地测试 GitLab，可选

如果你也想测 GitLab：

```bash
python scripts/dev_send_fixture.py gitlab tests/fixtures/gitlab_push.json --base-url http://127.0.0.1:8088 --token "$(grep '^GITLAB_SECRET_TOKEN=' .env | cut -d= -f2-)"
```

如果你只接 Codeup，这一步可以跳过。

## 路线 B：本地服务，但让 Codeup 真正打进来

这条路线只有在你有公网隧道时才适用，例如 ngrok、cloudflared tunnel、frp。核心要求是：Codeup 必须能从公网访问到你的本地服务。

假设你的公网隧道地址是：

```text
https://abc.example-tunnel.com
```

那 Codeup 新建 Webhook 填：

| Codeup 表单项 | 填什么 |
| --- | --- |
| URL / Webhook URL / 请求地址 | `https://abc.example-tunnel.com/webhooks/codeup` |
| 触发事件 | 只选 push 事件 |
| Secret Token / Token / 密钥 | 运行 `grep '^CODEUP_SECRET_TOKEN=' .env | cut -d= -f2-` 得到的值 |
| SSL 校验 | 正常 HTTPS 隧道保持开启 |

然后在 Codeup 后台点测试，或者向仓库 push 一次测试提交。

回到本地看日志：

```bash
docker compose logs --no-color --tail=200
```

如果看到 `webhook.accepted provider=codeup`，说明 Codeup 已经能打到你的本地服务。

注意：这时依然建议保持 `DELIVERY_MODE=dry_run`，先不要发真实飞书。

## 路线 C：部署到生产服务器，先 dry-run 验证

这条路线适合真正上线。假设你有一台服务器和一个域名，例如：

```text
repo-broadcast.example.com
```

生产建议先 dry-run。也就是说，先让 Codeup 真实打到生产服务器，但服务不发飞书，只记录消息和日志。确认没问题后再切 live。

### C1. 把代码放到服务器

在服务器上进入你放代码的位置，例如：

```bash
cd /opt
git clone <this-repo-url> feishu-repo-broadcast-service
cd feishu-repo-broadcast-service
```

如果你不是用 git clone，而是用其他方式上传代码，也可以，只要最后进入仓库根目录即可。

### C2. 创建 `.env`

```bash
cp .env.example .env
```

编辑 `.env`，生产服务器建议这样：

```dotenv
DELIVERY_MODE=dry_run
PUBLIC_HOST=repo-broadcast.example.com
HTTP_PORT=80
HTTPS_PORT=443
```

`PUBLIC_HOST` 必须换成你的真实域名。域名 DNS 要指向这台服务器。

### C3. 创建生产密钥文件

创建密钥目录：

```bash
mkdir -p secrets
```

创建 Codeup token。这个 token 是你自己定的一段随机字符串，后面 Codeup 后台也要填同一个值：

```bash
python - <<'PY' > secrets/codeup_secret_token.txt
import secrets
print(secrets.token_urlsafe(32), end="")
PY
```

如果不用 GitLab，也可以先生成一个占位 token：

```bash
python - <<'PY' > secrets/gitlab_secret_token.txt
import secrets
print(secrets.token_urlsafe(32), end="")
PY
```

生产 dry-run 阶段可以先不创建飞书 Webhook URL。如果你已经有飞书机器人 URL，也可以先创建，但 `dry_run` 不会调用它：

```bash
printf '%s' '<feishu-webhook-url>' > secrets/feishu_webhook_url.txt
```

如果飞书机器人启用了签名：

```bash
printf '%s' '<feishu-signing-secret>' > secrets/feishu_signing_secret.txt
```

### C4. 复制并调整 `compose.override.yaml`

复制：

```bash
cp compose.override.example.yaml compose.override.yaml
```

打开 `compose.override.yaml`，先把：

```yaml
DELIVERY_MODE: live
```

改成：

```yaml
DELIVERY_MODE: dry_run
```

这样可以使用 Docker Compose secrets 读取 token，但暂时不发飞书。

如果还没有创建 `secrets/feishu_webhook_url.txt`，也要先注释掉这两处：

```yaml
FEISHU_WEBHOOK_URL_FILE: /run/secrets/feishu_webhook_url
```

以及：

```yaml
- feishu_webhook_url
```

如果已经创建了 `secrets/feishu_webhook_url.txt`，可以不注释。

如果启用了飞书签名，再取消签名相关三处注释：

```yaml
FEISHU_SIGNING_SECRET_FILE: /run/secrets/feishu_signing_secret
```

```yaml
- feishu_signing_secret
```

```yaml
feishu_signing_secret:
  file: ./secrets/feishu_signing_secret.txt
```

### C5. 启动生产 dry-run 服务

```bash
docker compose up -d --build
```

检查：

```bash
docker compose ps
curl -fsS https://repo-broadcast.example.com/health
curl -fsS https://repo-broadcast.example.com/ready
```

把 `repo-broadcast.example.com` 换成你的真实域名。

### C6. 在 Codeup 新建 Webhook

先查看你要填到 Codeup 的 token：

```bash
cat secrets/codeup_secret_token.txt
```

然后去 Codeup 仓库后台新建 Webhook：

| Codeup 表单项 | 填什么 |
| --- | --- |
| URL / Webhook URL / 请求地址 | `https://repo-broadcast.example.com/webhooks/codeup` |
| 触发事件 | 只选 push 事件 |
| Secret Token / Token / 密钥 | `cat secrets/codeup_secret_token.txt` 输出的内容 |
| SSL 校验 | 保持开启 |

不要选择 PR、MR、评论、review 等事件。

### C7. 推一次测试提交

向 Codeup 仓库 push 一个很小的测试提交，然后看服务日志：

```bash
docker compose logs --no-color --tail=200
```

你要确认：

- 日志里有 `webhook.accepted provider=codeup`。
- 没有 `invalid Codeup secret token`。
- 没有 `unsupported Codeup event`。
- 服务没有真的发飞书，因为现在还是 `dry_run`。

如果你推送同一个事件或平台重试，同一个事件应该显示 `duplicate`，不会重复投递。

## 路线 D：生产服务器切换到 live，真正发送飞书

只有路线 C 全部验证通过后，才做这一步。

### D1. 创建飞书密钥文件

如果还没创建飞书 Webhook URL：

```bash
printf '%s' '<feishu-webhook-url>' > secrets/feishu_webhook_url.txt
```

如果飞书机器人启用了签名：

```bash
printf '%s' '<feishu-signing-secret>' > secrets/feishu_signing_secret.txt
```

### D2. 修改 `compose.override.yaml`

把：

```yaml
DELIVERY_MODE: dry_run
```

改成：

```yaml
DELIVERY_MODE: live
```

确认飞书 Webhook URL secret 已启用：

```yaml
FEISHU_WEBHOOK_URL_FILE: /run/secrets/feishu_webhook_url
```

以及：

```yaml
- feishu_webhook_url
```

如果启用了飞书签名，也确认签名 secret 已启用。

### D3. 重启服务

```bash
docker compose up -d --build
```

### D4. 发送一次真实 push 测试

向 Codeup 仓库 push 一次小提交。

确认：

1. 飞书群收到一条消息。
2. 服务日志显示 `delivery.delivered`。
3. 没有重复消息。

查看日志：

```bash
docker compose logs --no-color --tail=200
```

建议保存两份上线证据：

- 服务日志。
- 人工确认飞书群收到消息的记录。

## 常见问题

### 我本地没有 `secrets/codeup_secret_token.txt`，正常吗？

正常。

本地 dry-run 默认使用 `.env` 里的 `CODEUP_SECRET_TOKEN`。`secrets/codeup_secret_token.txt` 是生产部署使用 Docker Compose secrets 时才需要自己创建的文件。它不会被提交到 Git。

### fixture 脚本是什么？

fixture 脚本就是“本地假装 Codeup 发来了一次 push Webhook”。

它不会访问 Codeup，也不需要 Codeup 后台配置。它只是读取仓库里的测试 JSON，然后直接请求你的本地服务。

### `/health`、`/ready`、fixture POST、重复回放是什么意思？

- `/health`：确认服务进程活着。
- `/ready`：确认服务能打开 SQLite。
- fixture POST：用测试数据模拟一次 Codeup 或 GitLab push Webhook。
- 重复回放：把同一个 fixture 再发一次，确认服务返回 `duplicate`，不会重复投递。

### 为什么要先 dry-run？

因为 dry-run 可以确认 Webhook、token、消息格式、去重、日志都正常，但不会真的往飞书群发消息。这样不会误打扰群成员。

### 什么时候才去 Codeup 后台新建 Webhook？

满足下面任一条件再去：

- 服务已经部署到公网服务器，并且有真实域名。
- 本地服务已经通过公网隧道暴露给 Codeup。

如果只是普通本地启动，不要在 Codeup 后台填 `127.0.0.1`。

## Webhook 配置速查

Codeup：

- URL：`https://<host>/webhooks/codeup`
- 触发器：push 事件
- 密钥 token：存储在 `.env` 的 `CODEUP_SECRET_TOKEN`，或生产服务器上的 `secrets/codeup_secret_token.txt`

GitLab：

- URL：`https://<host>/webhooks/gitlab`
- 触发器：push 事件
- 密钥 token：存储在 `.env` 的 `GITLAB_SECRET_TOKEN`，或生产服务器上的 `secrets/gitlab_secret_token.txt`

## 飞书消息长什么样

每条出站飞书消息包含两个部分：

1. `Technical Explanation Protocol`：操作人、动作、仓库、分支、版本范围、提交数量，以及简洁的提交详情。
2. `Original Event`：提供方、ref、before/after SHA，以及有界的原始载荷块。

第一部分给人快速阅读，第二部分给排查问题时使用。

## 配置项速查

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

## 常用命令

启动或更新服务：

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs --no-color --tail=200
```

停止服务：

```bash
docker compose down
```

检查容器状态：

```bash
docker compose ps
```

本地开发和测试：

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
python -m compileall src tests
pytest -q
```

## 如果你要让 agent 帮另一个仓库安装

可以把下面这段提示词给 agent：

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
