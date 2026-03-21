import subprocess
from pathlib import Path

from etsync.data_repo import commit_sync, diff_last_sync, ensure_repo


def _run_git(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(data_dir),
        capture_output=True,
        text=True,
        check=True,
    )


class TestEnsureRepo:
    def test_creates_git_repo(self, tmp_path: Path):
        data_dir = tmp_path / "shop_data"
        ensure_repo(data_dir)
        assert (data_dir / ".git").exists()

    def test_creates_initial_commit(self, tmp_path: Path):
        data_dir = tmp_path / "shop_data"
        ensure_repo(data_dir)
        result = _run_git(data_dir, "log", "--oneline")
        assert "init: empty data repo" in result.stdout

    def test_idempotent(self, tmp_path: Path):
        data_dir = tmp_path / "shop_data"
        ensure_repo(data_dir)
        ensure_repo(data_dir)
        result = _run_git(data_dir, "rev-list", "--count", "HEAD")
        assert int(result.stdout.strip()) == 1


class TestCommitSync:
    def test_commits_new_files(self, tmp_path: Path):
        data_dir = tmp_path / "shop_data"
        ensure_repo(data_dir)
        (data_dir / "listing.json").write_text('{"id": 1}\n')
        committed = commit_sync(data_dir, count=1, synced_at="2026-03-21T10:00:00+00:00")
        assert committed is True
        result = _run_git(data_dir, "log", "--oneline", "-1")
        assert "sync: 1 listings @ 2026-03-21T10:00:00+00:00" in result.stdout

    def test_commits_modified_files(self, tmp_path: Path):
        data_dir = tmp_path / "shop_data"
        ensure_repo(data_dir)
        (data_dir / "listing.json").write_text('{"id": 1}\n')
        commit_sync(data_dir, count=1, synced_at="2026-03-21T09:00:00+00:00")
        (data_dir / "listing.json").write_text('{"id": 1, "title": "updated"}\n')
        committed = commit_sync(data_dir, count=1, synced_at="2026-03-21T10:00:00+00:00")
        assert committed is True

    def test_no_commit_when_nothing_changed(self, tmp_path: Path):
        data_dir = tmp_path / "shop_data"
        ensure_repo(data_dir)
        committed = commit_sync(data_dir, count=0, synced_at="2026-03-21T10:00:00+00:00")
        assert committed is False

    def test_commit_tracks_deleted_files(self, tmp_path: Path):
        data_dir = tmp_path / "shop_data"
        ensure_repo(data_dir)
        (data_dir / "listing.json").write_text('{"id": 1}\n')
        commit_sync(data_dir, count=1, synced_at="2026-03-21T09:00:00+00:00")
        (data_dir / "listing.json").unlink()
        committed = commit_sync(data_dir, count=0, synced_at="2026-03-21T10:00:00+00:00")
        assert committed is True


class TestDiffLastSync:
    def test_single_sync_shows_content(self, tmp_path: Path):
        data_dir = tmp_path / "shop_data"
        ensure_repo(data_dir)
        (data_dir / "listing.json").write_text('{"id": 1}\n')
        commit_sync(data_dir, count=1, synced_at="2026-03-21T09:00:00+00:00")
        result = diff_last_sync(data_dir)
        assert "listing.json" in result

    def test_two_syncs_shows_diff(self, tmp_path: Path):
        data_dir = tmp_path / "shop_data"
        ensure_repo(data_dir)
        (data_dir / "listing.json").write_text('{"title": "First"}\n')
        commit_sync(data_dir, count=1, synced_at="2026-03-21T09:00:00+00:00")
        (data_dir / "listing.json").write_text('{"title": "Updated"}\n')
        commit_sync(data_dir, count=1, synced_at="2026-03-21T10:00:00+00:00")
        result = diff_last_sync(data_dir)
        assert "First" in result
        assert "Updated" in result

    def test_no_history(self, tmp_path: Path):
        data_dir = tmp_path / "empty"
        data_dir.mkdir()
        result = diff_last_sync(data_dir)
        assert "one sync" in result.lower() or "no previous" in result.lower()
