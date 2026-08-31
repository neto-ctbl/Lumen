from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from agent.watcher.hash import DEFAULT_CHUNK_SIZE, sha256_file
from agent.watcher.payload_builder import PayloadBuildError, build_watcher_event_payload
from backend.tests.watcher_agent_test_utils import watcher_pdf_path, write_synthetic_pdf


def test_sha256_is_deterministic_streaming_and_content_sensitive(tmp_path: Path) -> None:
    path = tmp_path / "large.pdf"
    path.write_bytes(b"a" * (DEFAULT_CHUNK_SIZE + 7))
    first = sha256_file(path)
    assert first == hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_bytes(b"b" * (DEFAULT_CHUNK_SIZE + 7))
    assert sha256_file(path) != first


def test_payload_fails_safely_when_file_changes_during_processing(tmp_path: Path, monkeypatch) -> None:
    file_path = watcher_pdf_path(tmp_path)
    write_synthetic_pdf(file_path)

    def mutate_after_hash(path: Path) -> str:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.write_bytes(path.read_bytes() + b" ")
        return digest

    monkeypatch.setattr("agent.watcher.payload_builder.sha256_file", mutate_after_hash)
    with pytest.raises(PayloadBuildError, match="FILE_CHANGED_DURING_PROCESSING"):
        build_watcher_event_payload(tmp_path, file_path)
