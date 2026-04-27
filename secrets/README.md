# Docker Compose 密钥

这个目录用来放生产环境密钥文件。密钥文件会被 Docker Compose 挂载进容器，服务在运行时读取它们。

不要把真实密钥提交到 Git。`secrets/*.txt` 已经被 `.gitignore` 忽略，只有这个说明文件会被提交。

所以你在仓库里找不到 `secrets/codeup_secret_token.txt` 是正常的。这个文件不是代码仓库自带文件，而是部署时由你在本机或服务器上自己创建。

## 需要创建哪些文件

至少创建这三个文件：

```text
secrets/codeup_secret_token.txt
secrets/gitlab_secret_token.txt
secrets/feishu_webhook_url.txt
```

如果飞书机器人启用了签名，再创建这个文件：

```text
secrets/feishu_signing_secret.txt
```

## 每个文件填什么

`secrets/codeup_secret_token.txt`：

- 填 Codeup Webhook 配置里的 secret token。
- 这个值必须和 Codeup 仓库后台配置的一模一样。
- 这个值可以由你自己生成；它不是 Codeup 自动生成后放进本仓库的文件。
- 如果当前实例不用 Codeup，可以先填一个随机长字符串占位。

`secrets/gitlab_secret_token.txt`：

- 填 GitLab Webhook 配置里的 secret token。
- 这个值必须和 GitLab 仓库后台配置的一模一样。
- 这个值可以由你自己生成；它不是 GitLab 自动生成后放进本仓库的文件。
- 如果当前实例不用 GitLab，可以先填一个随机长字符串占位。

`secrets/feishu_webhook_url.txt`：

- 填飞书自定义机器人的完整 Webhook URL。
- 只有 `DELIVERY_MODE=live` 时才会真正使用。

`secrets/feishu_signing_secret.txt`：

- 只有飞书机器人启用了签名时才需要。
- 填飞书机器人后台显示的 signing secret。

## 逐步创建

进入仓库根目录后，先创建目录：

```bash
mkdir -p secrets
```

创建 Codeup token 文件：

```bash
printf '%s' '<codeup-token>' > secrets/codeup_secret_token.txt
```

创建 GitLab token 文件：

```bash
printf '%s' '<gitlab-token>' > secrets/gitlab_secret_token.txt
```

创建飞书 Webhook URL 文件：

```bash
printf '%s' '<feishu-webhook-url>' > secrets/feishu_webhook_url.txt
```

如果启用了飞书签名，再创建：

```bash
printf '%s' '<feishu-signing-secret>' > secrets/feishu_signing_secret.txt
```

## 启用 Compose secrets

复制生产 override 文件：

```bash
cp compose.override.example.yaml compose.override.yaml
```

如果没有启用飞书签名，不需要改 `compose.override.yaml`。

如果启用了飞书签名，需要打开 `compose.override.yaml`，取消三处注释：

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

然后启动：

```bash
docker compose up -d --build
```

默认 `compose.yaml` 不依赖这些真实密钥，方便全新检出后先用 `dry_run` 安全测试。进入生产 `live` 模式前，请确认密钥文件已经存在且内容正确。
