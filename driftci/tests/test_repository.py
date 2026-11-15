from __future__ import annotations

import io
import zipfile

import pytest

from server.repository import RepositoryError, parse_github, unpack


def archive(path: str, content: str = 'const MODEL = "gpt-4.1";') -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as bundle:
        bundle.writestr(path, content)
    return output.getvalue()


def test_github_url_validation():
    assert parse_github("https://github.com/owner/repo") == ("owner", "repo")
    assert parse_github("https://github.com/owner/repo.git") == ("owner", "repo")
    for url in ("/tmp/repo", "file:///tmp/repo", "https://evil.example/owner/repo", "https://github.com/owner/repo/issues"):
        with pytest.raises(RepositoryError):
            parse_github(url)


def test_bounded_zip_inventory_and_traversal_rejection():
    files = unpack(archive("orders-main/src/model.ts"))
    assert files == {"src/model.ts": 'const MODEL = "gpt-4.1";'}
    with pytest.raises(RepositoryError):
        unpack(archive("orders-main/../outside.ts"))
