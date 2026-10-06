"""Download NASA C-MAPSS and verify file checksums.

Usage: uv run python -m cmapss.download
"""

import hashlib
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

from cmapss.data import DATA_DIR

URL = (
    "https://phm-datasets.s3.amazonaws.com/NASA/"
    "6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"
)

# Recorded on first download (2026-10-01). A mismatch means the upstream data changed
# or the download is corrupt -- either way, results are no longer comparable.
SHA256 = {
    "RUL_FD001.txt": "a19c8ec94931949d0485bdc35118206e9c81c4547b422efb9cf86f4ceddbceca",
    "RUL_FD002.txt": "c851dd96a6ea6998d3c4a8f834d3c8013aa90e93a6ed950dc826ad0655b2906b",
    "RUL_FD003.txt": "df1e0566306b174a2de41c67a3e7a51877889598b78643fc3e5685259091b7cb",
    "RUL_FD004.txt": "196b836b85a95ac7fdbbf29c5fdf1657382eafa445644d114ffaaf50dc2975e1",
    "test_FD001.txt": "3cda7109ce17bafb5443f2ac926cfcf88154b941b8c4cf95eb55d1ddd6f52851",
    "test_FD002.txt": "de7b5bf7e998a985c378488480528b7c02cff1406a46740def362dda8d9b4e02",
    "test_FD003.txt": "299babd63c8d987cef079c4a425429f33b3a34797d803bbe2ad48c29dbd0d790",
    "test_FD004.txt": "1dc675fff0624bac10786927c6715b37d1297657137400d2b1a3138d777a3ba5",
    "train_FD001.txt": "963b5e22825b34d8b21c69e1aeb4af3e647050eb672ee8834ba4b5d91d2de0f8",
    "train_FD002.txt": "dac6c4dbc4e7c1bdeb5747da3d313d05c395bb99801b44a002b26a2ba13d788f",
    "train_FD003.txt": "2abbe9968cc5e8eb091980f51b20f62bb4127336d3482cb52071d53bf23329e2",
    "train_FD004.txt": "27ef6160b6a1dcb2613a88de9c239f763b223f02cdc41dc5cdedc5dc189b6218",
}


def verify(data_dir: Path = DATA_DIR) -> list[str]:
    """Return a list of problems; empty means every file is present and matches."""
    problems = []
    for name, expected in SHA256.items():
        path = data_dir / name
        if not path.exists():
            problems.append(f"missing: {name}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            problems.append(f"checksum mismatch: {name}")
    return problems


def download(data_dir: Path = DATA_DIR) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {URL}")
    with urllib.request.urlopen(URL) as resp:
        outer = zipfile.ZipFile(io.BytesIO(resp.read()))
    # The archive wraps a second zip that holds the actual data.
    inner_name = next(n for n in outer.namelist() if n.endswith("CMAPSSData.zip"))
    with zipfile.ZipFile(io.BytesIO(outer.read(inner_name))) as inner:
        for member in inner.namelist():
            target = data_dir / Path(member).name
            with inner.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)


def main() -> int:
    if verify():
        download()
    problems = verify()
    for p in problems:
        print(p, file=sys.stderr)
    if not problems:
        print(f"C-MAPSS OK at {DATA_DIR}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
