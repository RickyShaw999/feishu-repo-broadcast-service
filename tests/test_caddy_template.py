from pathlib import Path


def test_caddy_template_routes_health_and_webhooks() -> None:
    caddyfile = Path("deploy/Caddyfile.example").read_text(encoding="utf-8")

    assert "reverse_proxy app:8080" in caddyfile
    assert "handle /health" in caddyfile
    assert "handle /webhooks/*" in caddyfile


def test_compose_exposes_http_and_https_ports() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert "${HTTP_PORT:-80}:80" in compose
    assert "${HTTPS_PORT:-443}:443" in compose
    assert "PUBLIC_HOST:?Set PUBLIC_HOST" in compose
    assert "dev-codeup-token" not in compose
    assert "dev-gitlab-token" not in compose
