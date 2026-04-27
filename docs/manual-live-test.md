# 手动飞书 Live 测试

仅在 dry-run 路径通过后执行此测试。

## 前置条件

- 飞书机器人已添加到目标群聊。
- `secrets/feishu_webhook_url.txt` 包含完整的自定义机器人 Webhook URL。
- 如果启用了机器人签名，`secrets/feishu_signing_secret.txt` 包含签名密钥。
- 提供方密钥文件包含与 Codeup 或 GitLab 中配置一致的 token。

## 步骤

1. 确认 dry-run 成功：

   ```bash
   docker compose logs --no-color --tail=200
   ```

2. 启用 live 模式：

   ```bash
   cp compose.override.example.yaml compose.override.yaml
   DELIVERY_MODE=live docker compose up -d --build
   ```

3. 发送一个受控 fixture，或发送一次真实的提供方 push 事件。

4. 确认：

   - 飞书群收到一条消息。
   - 服务日志显示 `delivery.delivered`。
   - 回放同一个 fixture 返回 `duplicate`，且不会发送第二条消息。

5. 保存服务日志和人工飞书确认结果，作为 live 测试证据。
