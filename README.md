# 飞书仓库广播服务

`feishu-repo-broadcast-service` 用来接收 Codeup 或 GitLab 的 `push` Webhook，并把关键信息转发到飞书群机器人。

它适合下面这种场景：

- 一个代码仓库对应一个飞书群
- 只关心 `push` 事件
- 需要先 `dry_run` 验证，再切到 `live`
- 希望部署方式足够简单，团队成员拿到 README 就能复现

## 给 Agent 的入口

当仓库已经 clone 到目标服务器后，推荐将本 README 作为 agent 的执行依据，由 agent 按下述约定完成部署、验证和交接，而不是把它仅作为人工逐项操作手册。

### Agent 目标

agent 应该把当前仓库部署成一个可工作的服务，并完成以下事项：

1. 生成 `.env`
2. 生成 `secrets/*.txt`
3. 准备 `compose.override.yaml`
4. 构建并启动容器
5. 验证 `/health` 和 `/ready`
6. 如果宿主机已有 nginx，则配置反代
7. 指导用户配置 Codeup / GitLab Webhook
8. 先完成 `dry_run`
9. 在用户提供飞书 webhook 并确认后切到 `live`
10. 用真实 push 完成最终验收

### Agent 默认假设

除非用户明确说明不是，否则 agent 应该默认：

- 当前服务部署在 Linux 服务器
- 当前仓库已经 clone 到服务器本地
- 优先走 Docker Compose 部署
- 如果宿主机已有 nginx，不抢占宿主机 `80/443`
- 优先使用 `PUBLIC_HOST=:80`、`HTTP_PORT=8088`、`HTTPS_PORT=8443`
- 再通过宿主机 nginx 把正式域名反代到 `127.0.0.1:8088`
- 先从 `DELIVERY_MODE=dry_run` 开始
- Codeup 只配置 `推送事件`
- GitLab 只配置 `Push events`

### Agent 只需要向用户索取的最少信息

如果缺少这些信息，agent 可以向用户询问；除此之外应尽量自动完成：

- 域名是什么
- 当前接的是 Codeup 还是 GitLab
- 飞书机器人 webhook URL 是什么
- 飞书机器人是否开启签名
- 是否允许修改宿主机 nginx
- 如果需要 `sudo`，用户是否愿意亲自执行那几条命令

### Agent 自动执行边界

agent 应自动完成：

- 检查仓库结构
- 检查 Docker / Compose 是否可用
- 生成和修改仓库内文件
- 构建容器
- 发起本地健康检查
- 使用 fixture 或 `curl` 模拟 webhook
- 生成 nginx 配置模板
- 给出需要用户去外部系统操作的精确字段

agent 不应假设自己能自动完成：

- 飞书后台创建机器人
- Codeup / GitLab 后台点保存 webhook
- 云控制台放通安全组
- 输入用户的 `sudo` 密码

### Agent 停止条件

agent 应在下面任一条件满足前持续推进，不要停在“分析完成”：

1. `dry_run` 已验证通过
2. `live` 已验证通过
3. 用户明确要求暂停
4. 被外部系统权限阻塞，并且必须由用户亲自操作

### Agent 完成标准

agent 只有在下面这些都满足时，才应宣称部署完成：

- 容器已启动
- `/health` 返回 `ok`
- `/ready` 返回 `ready`
- webhook 校验 token 正常
- webhook 可接受真实 push
- 同一事件重复发送返回 `duplicate`
- `live` 模式下飞书群收到真实消息

### 直接贴给 Agent 的提示词

下面这段可以直接复制给任意 coding agent：

```text
你现在在一台服务器上，仓库 feishu-repo-broadcast-service 已经 clone 完成。

请直接阅读 README，并按 README 中的推荐路径自动完成部署。要求：

- 优先走 Docker Compose
- 如果宿主机已有 nginx，不要抢占 80/443，改走 8088/8443 + 宿主机 nginx 反代
- 先从 dry_run 开始，验证 /health、/ready、一次 webhook 模拟、一次 duplicate 回放
- 外部系统中必须由我手动完成的动作，你明确告诉我填写什么，不要泛泛而谈
- 如果需要我操作，只在真正需要我提供内容、点外部系统按钮、输入 sudo 密码时再停下来
- 完成 dry_run 后，再引导我切到 live
- live 阶段要验证飞书群是否真的收到了消息
- 如果 Codeup 测试按钮失败，要继续排查真实请求头、测试 payload、反代、DNS、安全组，不要停在猜测

完成后给我一份结果摘要，包括：
- 当前访问地址
- Webhook 应该填写的 URL 和 token
- 是否已经 live
- 剩余需要我亲自完成的动作
```

## 功能概览

- 支持 Codeup `push` Webhook
- 支持 GitLab `push` Webhook
- SQLite 持久化去重、outbox、重试、重启恢复
- Docker Compose 部署
- 生产环境使用 Docker Compose secrets 读取 token / 飞书 webhook
- 飞书消息使用交互卡片格式，保留操作人、仓库、分支、时间、提交摘要和跳转按钮等关键信息

当前不支持：

- PR / MR / 评论 / Review 事件
- 一个实例绑定多个仓库
- 一个实例绑定多个飞书机器人
- UI 管理后台

## 服务行为

### 输入

- Codeup: `POST /webhooks/codeup`
- GitLab: `POST /webhooks/gitlab`

### 输出

`dry_run`：

- 接收并校验 Webhook
- 生成飞书消息
- 写入 SQLite
- 不真正调用飞书

`live`：

- 执行上述全部流程
- 并真实调用飞书机器人 Webhook

### 健康检查

- `/health`：进程存活
- `/ready`：SQLite 可打开

## 飞书消息长什么样

当前飞书消息为交互卡片，不再附带原始 JSON。卡片内容示例：

```text
代码推送通知：pengleni
操作人：RickyShaw
仓库：pengleni
分支：develop
推送时间：2026-04-27 20:41
提交数量：1
版本范围：5b3cbd5b -> f2514848
提交内容：
- [f2514848] RickyShaw [2026-04-27 20:41]: 测试飞书机器人
按钮：查看最新提交 / 打开仓库
```

## 快速开始

### 前置条件

- Linux 服务器
- Docker
- Docker Compose v2
- 一个飞书群自定义机器人
- 一个可从 Codeup / GitLab 访问到的域名或公网入口

推荐额外准备：

- 宿主机 nginx 反向代理
- 安全组已放通 `80`；如需 HTTPS 再放通 `443`

## 生产部署：推荐路径

下面是本仓库已经在线验证通过的一条路径，适合“宿主机已有 nginx，对外开放 80 端口”的场景。

拓扑如下：

```text
Codeup / GitLab
    -> http://feishu.example.com/webhooks/codeup
    -> 宿主机 nginx :80
    -> 127.0.0.1:8088
    -> docker compose 中的 caddy
    -> app:8080
```

### 1. 克隆代码

```bash
git clone <repo-url> feishu-repo-broadcast-service
cd feishu-repo-broadcast-service
```

### 2. 准备 `.env`

```bash
cp .env.example .env
```

如果宿主机 `80/443` 已被现有 nginx 占用，建议使用下面这组端口：

```dotenv
PUBLIC_HOST=:80
HTTP_PORT=8088
HTTPS_PORT=8443
```

含义是：

- 容器内 caddy 继续监听 `80/443`
- 宿主机只把它映射到 `8088/8443`
- 再由宿主机 nginx 把正式域名反代到 `127.0.0.1:8088`

如果你的服务器没有现成 nginx，也可以直接使用 `80/443`：

```dotenv
PUBLIC_HOST=feishu.example.com
HTTP_PORT=80
HTTPS_PORT=443
```

### 3. 创建 secrets

先创建目录：

```bash
mkdir -p secrets
```

生成 Codeup token：

```bash
python3 - <<'PY' > secrets/codeup_secret_token.txt
import secrets
print(secrets.token_urlsafe(32), end="")
PY
```

生成 GitLab token：

```bash
python3 - <<'PY' > secrets/gitlab_secret_token.txt
import secrets
print(secrets.token_urlsafe(32), end="")
PY
```

写入飞书机器人 webhook：

```bash
printf '%s' '<feishu-webhook-url>' > secrets/feishu_webhook_url.txt
```

如果飞书机器人启用了签名，再额外创建：

```bash
printf '%s' '<feishu-signing-secret>' > secrets/feishu_signing_secret.txt
```

### 4. 准备 `compose.override.yaml`

```bash
cp compose.override.example.yaml compose.override.yaml
```

推荐流程：

1. 第一轮验证先把 `DELIVERY_MODE: live` 改成 `dry_run`
2. 验证通过后再切回 `live`

如果没有启用飞书签名，保持这三处注释：

```yaml
# FEISHU_SIGNING_SECRET_FILE: /run/secrets/feishu_signing_secret
# - feishu_signing_secret
# feishu_signing_secret:
#   file: ./secrets/feishu_signing_secret.txt
```

### 5. 启动服务

如果你的 shell 里配置了本地代理，例如：

```bash
HTTP_PROXY=http://localhost:7777
HTTPS_PROXY=http://localhost:7777
```

请先清掉再构建，否则 Docker build 容器里访问 `localhost:7777` 会指向容器自己，可能导致 pip 下载到空响应。

```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
docker compose up -d --build
```

### 6. 宿主机 nginx 反代

如果宿主机已经有 nginx，直接使用仓库提供的模板：

- [deploy/nginx.feishu.zhibianai.com.conf.example](deploy/nginx.feishu.zhibianai.com.conf.example)

最常见做法：

```bash
sudo cp deploy/nginx.feishu.zhibianai.com.conf.example /etc/nginx/conf.d/feishu.example.com.conf
sudo nginx -t
sudo systemctl reload nginx
```

模板核心逻辑是：

```nginx
server {
    listen 80;
    server_name feishu.example.com;

    location / {
        proxy_pass http://127.0.0.1:8088;
    }
}
```

### 7. 配置 DNS / 安全组

必须确认：

- 域名已解析到当前服务器的公网入口 IP
- 安全组已放通公网入方向 `TCP 80`
- 如果将来要启用 HTTPS，再放通 `TCP 443`

如果你能 `ssh <公网IP> -p <端口>` 登录服务器，不代表 `80/443` 也已经放通。需要单独检查公网入方向规则。

### 8. 验证健康状态

```bash
curl -fsS http://127.0.0.1:8088/health
curl -fsS http://127.0.0.1:8088/ready
curl -fsS http://<你的域名>/health
```

正确结果：

```json
{"status":"ok"}
```

和：

```json
{"status":"ready"}
```

## Codeup 配置

### 新建 Webhook 时怎么填

| Codeup 表单项 | 填写方式 |
| --- | --- |
| URL | `http://<你的域名>/webhooks/codeup` 或 `https://<你的域名>/webhooks/codeup` |
| Secret Token | `secrets/codeup_secret_token.txt` 中的内容 |
| 触发器 | 只勾选 `推送事件` |
| 描述 | 可填 `feishu repo broadcast service` |

不要勾选：

- 标签推送事件
- 评论
- 合并请求事件

### Codeup 实际兼容情况

本仓库已经兼容下面两类 Codeup 请求：

1. 真实 `push` 事件
   Codeup 真实请求头可能使用：

   - `X-Codeup-Event: Push Hook`
   - `X-Codeup-Token: ...`

2. Codeup 后台“测试 Webhook”按钮
   这个按钮发出的 payload 可能只有：

```json
{"before":"...","after":"..."}
```

当前服务会把这类请求识别为 `probe` 并返回 `200`，不会误报 URL 错误。

## GitLab 配置

| GitLab 表单项 | 填写方式 |
| --- | --- |
| URL | `http://<你的域名>/webhooks/gitlab` 或 `https://<你的域名>/webhooks/gitlab` |
| Secret Token | `secrets/gitlab_secret_token.txt` 中的内容 |
| Trigger | 只勾选 `Push events` |

## 飞书机器人怎么创建

`secrets/feishu_webhook_url.txt` 里的内容来自飞书群自定义机器人。

创建流程：

1. 打开目标飞书群
2. 进入群设置
3. 添加机器人
4. 选择自定义机器人
5. 创建后复制 Webhook URL
6. 写入 `secrets/feishu_webhook_url.txt`

如果飞书后台启用了签名校验，再把签名 secret 写入：

```bash
printf '%s' '<feishu-signing-secret>' > secrets/feishu_signing_secret.txt
```

## 建议的上线顺序

### 阶段 1：dry-run

1. `compose.override.yaml` 设置 `DELIVERY_MODE: dry_run`
2. 启动服务
3. 验证 `/health`、`/ready`
4. 本地用 fixture 或 curl 模拟一次 Codeup 请求
5. 确认第二次回放返回 `duplicate`
6. 在 Codeup / GitLab 后台配置真实 webhook
7. 推一次真实提交，确认服务可以接收

### 阶段 2：live

1. 把 `compose.override.yaml` 改回 `DELIVERY_MODE: live`
2. `docker compose up -d --build`
3. 再 push 一次小提交
4. 确认飞书群收到了消息

## 本地验证命令

### 启动

```bash
docker compose up -d --build
```

### 健康检查

```bash
curl -fsS http://127.0.0.1:8088/health
curl -fsS http://127.0.0.1:8088/ready
```

### 模拟 Codeup 请求

如果宿主机 `python` 版本较旧，也可以直接用 `curl`，不依赖 `scripts/dev_send_fixture.py`：

```bash
curl -sS -X POST http://127.0.0.1:8088/webhooks/codeup \
  -H 'Content-Type: application/json' \
  -H 'X-Codeup-Event: Push Hook' \
  -H "X-Codeup-Token: $(cat secrets/codeup_secret_token.txt)" \
  --data @tests/fixtures/codeup_push.json
```

### 查看日志

```bash
docker compose logs --no-color --tail=200
```

## 常见问题

### 1. `docker compose up -d --build` 提示 Docker socket permission denied

把当前用户加入 `docker` 组，或直接用 `sudo docker ...`。

### 2. Docker 网络创建失败

如果看到：

```text
could not find an available, non-overlapping IPv4 address pool
```

当前仓库已经在 [compose.yaml](compose.yaml) 里固定了默认子网：

```yaml
192.168.251.0/24
```

正常情况下不需要再手工处理。

### 3. 宿主机 `80` 端口被占用

如果宿主机已有 nginx / caddy / 面板服务，不要强行让 compose 去抢 `80/443`。

请改用：

```dotenv
PUBLIC_HOST=:80
HTTP_PORT=8088
HTTPS_PORT=8443
```

然后由宿主机 nginx 反代到 `127.0.0.1:8088`。

### 4. Codeup 测试按钮报 URL 错误

可能原因：

- 公网 `80` 未放通
- 域名没有解析到正确入口
- nginx 未加载反代配置
- 运行中的容器还是旧版本

当前代码已经兼容 Codeup 的测试探测 payload。

### 5. 真实 push 返回 `unsupported Codeup event`

Codeup 真实 push 常用的头是：

```text
X-Codeup-Event: Push Hook
```

当前代码已经兼容 `X-Codeup-Event` 和 `Codeup-Event` 两种写法。

### 6. Docker build 时 pip 报 `Broken pipe` / sha256 不匹配 / 空文件 hash

优先检查宿主机是否设置了本地代理：

```bash
HTTP_PROXY=http://localhost:7777
HTTPS_PROXY=http://localhost:7777
```

这会让容器在 build 时访问到错误的 `localhost`。当前 [Dockerfile](Dockerfile) 已经显式清理构建代理，并切到清华 PyPI 镜像。

重新构建建议：

```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
docker compose build --no-cache
docker compose up -d
```

### 7. 本地 `python3` 过旧，fixture 脚本跑不起来

如果宿主机 Python 小于 3.11，直接使用上面的 `curl` 方式模拟 webhook 即可。

## 配置项速查

| 名称 | 默认值 | 用途 |
| --- | --- | --- |
| `DELIVERY_MODE` | `dry_run` | `dry_run` 只记录不发飞书，`live` 真实投递 |
| `DATABASE_PATH` | `/data/service.db` | SQLite 路径 |
| `WORKER_ENABLED` | `true` | 是否启用 outbox worker |
| `WORKER_INTERVAL_SECONDS` | `2` | worker 轮询间隔 |
| `LEASE_TIMEOUT_SECONDS` | `300` | 卡住的 in-progress 回收阈值 |
| `MAX_DELIVERY_ATTEMPTS` | `5` | 最大重试次数 |
| `CODEUP_SECRET_TOKEN` / `_FILE` | 空 | Codeup token |
| `GITLAB_SECRET_TOKEN` / `_FILE` | 空 | GitLab token |
| `FEISHU_WEBHOOK_URL` / `_FILE` | 空 | 飞书机器人 webhook |
| `FEISHU_SIGNING_SECRET` / `_FILE` | 空 | 飞书机器人签名 secret |
| `PUBLIC_HOST` | `example.com` | caddy 站点地址；本地可用 `:80` |
| `HTTP_PORT` | `80` | 宿主机 HTTP 端口 |
| `HTTPS_PORT` | `443` | 宿主机 HTTPS 端口 |

## 仓库内关键文件

- [compose.yaml](compose.yaml)：基础服务编排
- [compose.override.example.yaml](compose.override.example.yaml)：生产 secrets / live 示例
- [deploy/nginx.feishu.zhibianai.com.conf.example](deploy/nginx.feishu.zhibianai.com.conf.example)：宿主机 nginx 反代模板
- [Dockerfile](Dockerfile)：镜像构建
- [docs/operations.md](docs/operations.md)：运行时说明
- [secrets/README.md](secrets/README.md)：secrets 文件说明

## 给其他团队成员的最短交接话术

1. 克隆仓库
2. 创建 `.env`
3. 创建 `secrets/codeup_secret_token.txt`、`secrets/gitlab_secret_token.txt`、`secrets/feishu_webhook_url.txt`
4. 复制 `compose.override.example.yaml -> compose.override.yaml`
5. 宿主机已有 nginx 时，使用 `deploy/nginx.feishu.zhibianai.com.conf.example`
6. 放通公网 `80`
7. `unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy`
8. `docker compose up -d --build`
9. 验证 `/health`
10. Codeup 只勾选 `推送事件`
11. 先 `dry_run`，再 `live`
