"""
Atskirų failų ištraukimas iš nutolusio ZIP archyvo per HTTP Range užklausas.

AIT-LDS scenarijų archyvai yra 7–27 GB, o vertinimui reikia tik kelių žurnalų ir
jų žymių failų, todėl skaitomas tik centrinis katalogas ir pasirinkti nariai.
Kiekvieno nario vientisumas tikrinamas pagal ZIP CRC32.
"""
from __future__ import annotations

import fnmatch
import io
import struct
import time
import zipfile
import zlib
from collections import OrderedDict
from pathlib import Path

import requests

_LOCAL_HEADER = struct.Struct("<4sHHHHHIIIHH")


class HttpRangeFile(io.RawIOBase):
    """Read-only, seekable file object backed by HTTP Range requests (LRU block cache)."""

    def __init__(self, url: str, block_size: int = 4 * 1024 * 1024, session: requests.Session | None = None):
        self.session = session or requests.Session()
        resp = self.session.head(url, allow_redirects=True, timeout=120)
        resp.raise_for_status()
        self.url = resp.url
        self.size = int(resp.headers["Content-Length"])
        self.block_size = block_size
        self.pos = 0
        self._cache: OrderedDict[int, bytes] = OrderedDict()

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = max(0, base + offset)
        return self.pos

    def fetch(self, start: int, end_inclusive: int, retries: int = 5) -> bytes:
        for attempt in range(retries):
            try:
                resp = self.session.get(
                    self.url, headers={"Range": f"bytes={start}-{end_inclusive}"}, timeout=300)
            except (requests.ConnectionError, requests.Timeout):
                resp = None
            if resp is not None and resp.status_code == 206:
                return resp.content
            if resp is not None and resp.status_code == 200:
                raise IOError("Serveris nepalaiko HTTP Range užklausų")
            if attempt + 1 < retries:
                time.sleep(2 ** attempt * 5)
        status = resp.status_code if resp is not None else "ryšio klaida"
        raise IOError(f"Range užklausa nepavyko po {retries} bandymų ({status})")

    def _block(self, index: int) -> bytes:
        if index in self._cache:
            self._cache.move_to_end(index)
            return self._cache[index]
        start = index * self.block_size
        data = self.fetch(start, min(self.size, start + self.block_size) - 1)
        self._cache[index] = data
        if len(self._cache) > 8:
            self._cache.popitem(last=False)
        return data

    def readinto(self, buffer) -> int:
        if self.pos >= self.size:
            return 0
        view = memoryview(buffer)
        want = min(len(view), self.size - self.pos)
        written = 0
        while written < want:
            index, offset = divmod(self.pos, self.block_size)
            chunk = self._block(index)[offset:offset + want - written]
            view[written:written + len(chunk)] = chunk
            written += len(chunk)
            self.pos += len(chunk)
        return written


class RemoteZip:
    """ZIP archive accessed over HTTP; lists members and extracts selected ones."""

    def __init__(self, url: str, session: requests.Session | None = None):
        self.file = HttpRangeFile(url, session=session)
        self.zip = zipfile.ZipFile(self.file)

    def members(self, patterns: list[str] | None = None) -> list[zipfile.ZipInfo]:
        infos = [i for i in self.zip.infolist() if not i.is_dir()]
        if not patterns:
            return infos
        return [i for i in infos if any(fnmatch.fnmatch(i.filename, p) for p in patterns)]

    def extract(self, info: zipfile.ZipInfo, dest_root: Path, chunk: int = 8 * 1024 * 1024) -> Path:
        """Streams one member to `dest_root/<member path>`, verifying CRC32."""
        header = self.file.fetch(info.header_offset, info.header_offset + _LOCAL_HEADER.size - 1)
        fields = _LOCAL_HEADER.unpack(header)
        if fields[0] != b"PK\x03\x04":
            raise IOError(f"Neteisinga ZIP vietinė antraštė: {info.filename}")
        data_start = info.header_offset + _LOCAL_HEADER.size + fields[9] + fields[10]
        data_end = data_start + info.compress_size

        dest = dest_root / info.filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        if info.compress_type == zipfile.ZIP_DEFLATED:
            inflater = zlib.decompressobj(-15)
        elif info.compress_type == zipfile.ZIP_STORED:
            inflater = None
        else:
            raise IOError(f"Nepalaikomas suspaudimas ({info.compress_type}): {info.filename}")

        crc = 0
        with open(tmp, "wb") as out:
            pos = data_start
            while pos < data_end:
                raw = self.file.fetch(pos, min(data_end, pos + chunk) - 1)
                pos += len(raw)
                data = inflater.decompress(raw) if inflater else raw
                crc = zlib.crc32(data, crc)
                out.write(data)
            if inflater:
                tail = inflater.flush()
                crc = zlib.crc32(tail, crc)
                out.write(tail)
        if crc != info.CRC:
            tmp.unlink(missing_ok=True)
            raise IOError(f"CRC32 neatitinka: {info.filename}")
        tmp.replace(dest)
        return dest
