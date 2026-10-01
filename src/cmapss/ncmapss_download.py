"""Download N-CMAPSS (Arias Chao et al. 2021) and verify checksums.

The NASA archive is a 15.8 GB zip that contains one deflated inner zip, so members cannot be
range-requested. Instead we stream: HTTP -> outer unzip -> inner unzip -> disk, keeping only
the requested .h5 files. Each file is hash-checked, repacked to float32 in data/interim
(~6x smaller, see cmapss.ncmapss) and the raw copy deleted, so peak disk is ~one raw file
(<4 GB) plus the 4.6 GB of repacked data. Takes ~5 min at ~65 MB/s.

Usage:
  uv run python -m cmapss.ncmapss_download              # all subsets
  uv run python -m cmapss.ncmapss_download DS01 DS04    # only these
"""

import hashlib
import shutil
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

import h5py
from stream_unzip import stream_unzip

from cmapss.data import REPO_ROOT

URL = (
    "https://phm-datasets.s3.amazonaws.com/NASA/"
    "17.+Turbofan+Engine+Degradation+Simulation+Data+Set+2.zip"
)
DATA_DIR = REPO_ROOT / "data" / "raw" / "N-CMAPSS"
MIN_FREE_BYTES = 3 * 1024**3

# Recorded on first download (2026-10-01).
SHA256 = {
    "N-CMAPSS_DS01-005.h5": "3abdcee2a3c8136e8880e5d43ac8cdf12ab9f7f3ab37145f23b24c11335afbed",
    "N-CMAPSS_DS02-006.h5": "47971a68b239ecb756833218a95d68ded6eb7e63ee84e86671c8b188de1ca765",
    "N-CMAPSS_DS03-012.h5": "f67cc4bd0cf927f09eb8e0198bd62c777e1c6213177cfc46d81cc43bba52c333",
    "N-CMAPSS_DS04.h5": "2b58cbb78497679fadafe0761203b2ae3b0e4e1193039dc34ca25f17ecaeb2e6",
    "N-CMAPSS_DS05.h5": "ef99ead42ac184503035895797c16e9a7e42554a08074aa760d0bba39db42e23",
    "N-CMAPSS_DS06.h5": "91ccf478b21dd6337cfa608f20b647ec04228d59cf4ee59be87fad5f08b17b20",
    "N-CMAPSS_DS07.h5": "2f88abc61a532d2e30a6e5ff100a511be4921484a6c7071bc8504e300da4d3bd",
    "N-CMAPSS_DS08a-009.h5": "10ddf52e5441a05e3d0d8d797a34e0e5a9ac73dce8ae35d7b22d1ef224d24836",
    "N-CMAPSS_DS08c-008.h5": "150bf696dcf4bbac84518f439ac0d491410037881e214c5b10c048a71770bb38",
}

# Corrupt upstream: the archive's own CRC matches, but the HDF5 file is internally broken
# (stored EOF is 32 bytes past the real end; group index fails with "bad symbol table node
# signature"). It also compresses at 59% vs ~44% for every other file. Checked 2026-10-01
# with Info-ZIP `unzip -t` on the extracted inner archive.
KNOWN_CORRUPT = {"N-CMAPSS_DS08d-010.h5"}


def _http_chunks(url: str, size: int = 1 << 20):
    with urllib.request.urlopen(url) as resp:
        while chunk := resp.read(size):
            yield chunk


def _drain(chunks) -> None:
    for _ in chunks:
        pass


def download(
    wanted: list[str] | None = None,
    data_dir: Path = DATA_DIR,
    on_saved: Callable[[Path], None] | None = None,
) -> dict[str, str]:
    data_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for outer_name, _, outer_chunks in stream_unzip(_http_chunks(URL)):
        if not outer_name.endswith(b".zip"):
            _drain(outer_chunks)
            continue
        for name_b, _, chunks in stream_unzip(outer_chunks):
            name = Path(name_b.decode()).name
            keep = (
                name.endswith(".h5")
                and name not in KNOWN_CORRUPT
                and (not wanted or any(w in name for w in wanted))
            )
            if not keep:
                print(f"skip  {name_b.decode()}", flush=True)
                _drain(chunks)
                continue
            if shutil.disk_usage(data_dir).free < MIN_FREE_BYTES:
                raise OSError(f"Less than {MIN_FREE_BYTES >> 30} GB free; stopping before {name}")
            h = hashlib.sha256()
            with open(data_dir / f"{name}.part", "wb") as f:
                for c in chunks:
                    h.update(c)
                    f.write(c)
            (data_dir / f"{name}.part").rename(data_dir / name)
            hashes[name] = h.hexdigest()
            print(
                f"saved {name} {(data_dir / name).stat().st_size / 1e9:.2f} GB "
                f"sha256={hashes[name]}",
                flush=True,
            )
            if hashes[name] != SHA256.get(name):
                raise ValueError(f"{name}: sha256 {hashes[name]} != pinned {SHA256.get(name)}")
            if on_saved:
                on_saved(data_dir / name)
    return hashes


def verify(names: list[str] | None = None, data_dir: Path = DATA_DIR) -> list[str]:
    """A file is OK if its raw copy hashes correctly, or its repacked copy records the pinned
    source hash (repacks are checked element-wise against the hashed raw file when written)."""
    from cmapss.ncmapss import INTERIM_DIR

    problems = []
    for name, expected in SHA256.items():
        if names and not any(n in name for n in names):
            continue
        interim, raw = INTERIM_DIR / name, data_dir / name
        if interim.exists():
            with h5py.File(interim, "r") as f:
                if f.attrs.get("source_sha256") != expected:
                    problems.append(f"repacked file has wrong source hash: {name}")
        elif raw.exists():
            h = hashlib.sha256()
            with open(raw, "rb") as f:
                while b := f.read(1 << 24):
                    h.update(b)
            if h.hexdigest() != expected:
                problems.append(f"checksum mismatch: {name}")
        else:
            problems.append(f"missing: {name}")
    return problems


def main() -> int:
    from cmapss.ncmapss import INTERIM_DIR, repack_file

    def repack_and_drop(raw: Path) -> None:
        repack_file(raw, INTERIM_DIR / raw.name)
        raw.unlink()

    wanted = sys.argv[1:] or None
    if verify(wanted):
        download(wanted, on_saved=repack_and_drop)
    problems = verify(wanted)
    for p in problems:
        print(p, file=sys.stderr)
    if not problems:
        print(f"N-CMAPSS OK at {INTERIM_DIR}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
