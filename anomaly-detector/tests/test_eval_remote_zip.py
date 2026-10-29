"""
Nutolusio ZIP skaitytuvo testai su netikru HTTP Range serveriu.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from evaluation.remote_zip import RemoteZip


class _Resp:
    def __init__(self, status: int, content: bytes = b"", headers: dict | None = None, url: str = ""):
        self.status_code = status
        self.content = content
        self.headers = headers or {}
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeRangeSession:
    def __init__(self, blob: bytes, corrupt_at: int | None = None):
        self.blob = bytearray(blob)
        if corrupt_at is not None:
            self.blob[corrupt_at] ^= 0xFF
        self.requests = 0

    def head(self, url, allow_redirects=True, timeout=None):
        return _Resp(200, headers={"Content-Length": str(len(self.blob))}, url=url)

    def get(self, url, headers=None, timeout=None):
        self.requests += 1
        start, end = (int(x) for x in headers["Range"].removeprefix("bytes=").split("-"))
        return _Resp(206, bytes(self.blob[start:end + 1]))


def _archive() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dataset.yaml", "name: x\n")
        zf.writestr("gather/web/logs/auth.log", "Jan 24 04:37:40 web su[1]: ok\n" * 2000)
        zf.writestr("gather/web/logs/big.pcap", b"\x00" * 50000)
    return buf.getvalue()


def test_lists_and_extracts_selected_members(tmp_path):
    rz = RemoteZip("http://example/x.zip", session=FakeRangeSession(_archive()))
    wanted = rz.members(["gather/*/logs/auth.log*", "dataset.yaml"])
    assert sorted(i.filename for i in wanted) == ["dataset.yaml", "gather/web/logs/auth.log"]
    for info in wanted:
        rz.extract(info, tmp_path)
    assert (tmp_path / "gather/web/logs/auth.log").read_text().count("\n") == 2000


def test_crc_mismatch_is_rejected(tmp_path):
    blob = _archive()
    offset = blob.index(b"gather/web/logs/auth.log") + 60   # pirmo nario duomenyse
    rz = RemoteZip("http://example/x.zip", session=FakeRangeSession(blob, corrupt_at=offset))
    info = rz.members(["gather/web/logs/auth.log"])[0]
    with pytest.raises(Exception):
        rz.extract(info, tmp_path)
    assert not (tmp_path / "gather/web/logs/auth.log").exists()
