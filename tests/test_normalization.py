from service.domain.dedup import dedup_key
from service.providers import codeup, gitlab

from tests.conftest import load_fixture


def test_codeup_push_normalizes_to_canonical_model() -> None:
    event = codeup.normalize_push(load_fixture("codeup_push.json"))

    assert event.provider == "codeup"
    assert event.repository.name == "pengleni"
    assert event.branch == "develop"
    assert event.actor_name == "Codeup User"
    assert event.total_commits_count == 2
    assert event.commits[0].author_email == "codeup@example.com"
    assert len(dedup_key(event)) == 64


def test_gitlab_push_normalizes_to_canonical_model() -> None:
    event = gitlab.normalize_push(load_fixture("gitlab_push.json"))

    assert event.provider == "gitlab"
    assert event.repository.path_with_namespace == "group/sample-project"
    assert event.branch == "main"
    assert event.actor_username == "gitlab-user"
    assert event.total_commits_count == 1
    assert event.commits[0].message == "Add webhook receiver"
    assert len(dedup_key(event)) == 64

