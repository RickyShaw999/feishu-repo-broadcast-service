# Docker Compose 密钥

生产环境部署应将运行时密钥存储为由 Docker Compose 挂载的文件。

在本地创建这些文件，并确保它们不进入 Git：

- `secrets/codeup_secret_token.txt`
- `secrets/gitlab_secret_token.txt`
- `secrets/feishu_webhook_url.txt`
- `secrets/feishu_signing_secret.txt` 可选；仅当启用飞书机器人签名时，才在 `compose.override.yaml` 中取消它的注释

然后将 `compose.override.example.yaml` 复制为 `compose.override.yaml` 并运行：

```bash
docker compose up -d --build
```

已提交的 `compose.yaml` 会在没有这些文件的情况下以 dry-run 模式启动，因此全新检出也可以安全测试。
