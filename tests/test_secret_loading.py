from service.infrastructure.secrets import read_secret


def test_secret_file_overrides_direct_environment(monkeypatch, tmp_path) -> None:
    secret_file = tmp_path / "token.txt"
    secret_file.write_text("production-token\n", encoding="utf-8")
    monkeypatch.setenv("CODEUP_SECRET_TOKEN", "dev-token")
    monkeypatch.setenv("CODEUP_SECRET_TOKEN_FILE", str(secret_file))

    assert read_secret("CODEUP_SECRET_TOKEN") == "production-token"

