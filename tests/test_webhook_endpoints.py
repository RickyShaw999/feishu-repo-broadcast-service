from fastapi.testclient import TestClient

from service.config import Settings
from service.infrastructure.sqlite_store import SQLiteStore
from service.main import create_app

from tests.conftest import load_fixture


def make_client(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "service.db"),
        worker_enabled=False,
        codeup_secret_token="codeup-secret",
        gitlab_secret_token="gitlab-secret",
    )
    store = SQLiteStore(settings.database_path)
    store.initialize()
    app = create_app(settings=settings, store=store)
    return TestClient(app)


def test_codeup_webhook_rejects_missing_token(tmp_path, caplog) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/webhooks/codeup",
        headers={"Codeup-Event": "Push Hook"},
        json=load_fixture("codeup_push.json"),
    )

    assert response.status_code == 401
    assert "webhook.rejected provider=codeup reason=invalid_secret_token" in caplog.text


def test_codeup_webhook_accepts_valid_push_and_deduplicates(tmp_path) -> None:
    client = make_client(tmp_path)
    headers = {"Codeup-Event": "Push Hook", "X-Codeup-Token": "codeup-secret"}

    first = client.post("/webhooks/codeup", headers=headers, json=load_fixture("codeup_push.json"))
    second = client.post("/webhooks/codeup", headers=headers, json=load_fixture("codeup_push.json"))

    assert first.status_code == 200
    assert first.json()["status"] == "accepted"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


def test_gitlab_webhook_rejects_wrong_event(tmp_path, caplog) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/webhooks/gitlab",
        headers={"X-Gitlab-Event": "Merge Request Hook", "X-Gitlab-Token": "gitlab-secret"},
        json=load_fixture("gitlab_push.json"),
    )

    assert response.status_code == 400
    assert "webhook.rejected provider=gitlab reason=unsupported_event" in caplog.text


def test_gitlab_webhook_accepts_valid_push(tmp_path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/webhooks/gitlab",
        headers={"X-Gitlab-Event": "Push Hook", "X-Gitlab-Token": "gitlab-secret"},
        json=load_fixture("gitlab_push.json"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
