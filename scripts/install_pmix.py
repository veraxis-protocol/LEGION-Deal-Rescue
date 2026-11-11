"""Install ONLY the hash-pinned pmix from an already downloaded WO-CAD-001 ZIP.

python -B scripts/install_pmix.py /path/PAYPAL_CAD_001_RELEASE_20261110.zip
No network, archive path extraction or execution of unverified code.
"""
import argparse
import hashlib
from pathlib import Path
import zipfile

ZIP_SHA256='02afba7871dbad8d2f41c913d952cf5857378b41ee3e50a030b217fce51e5871'
BIN_SHA256='cc44b80916fd03c03b74bfa5b011061583c2b96cfc0ca0685ca93cfe1ca0ae43'
ROOT=Path(__file__).resolve().parents[1]


def install(archive):
    if archive.stat().st_size > 32*1024*1024:
        raise ValueError('RELEASE_ARCHIVE_SIZE_LIMIT')
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=ZIP_SHA256:
        raise ValueError('RELEASE_ARCHIVE_CHECKSUM_MISMATCH')
    with zipfile.ZipFile(archive) as z:
        binary=z.read('tools/pmix-x86_64-unknown-linux-gnu/pmix')
        if hashlib.sha256(binary).hexdigest()!=BIN_SHA256:
            raise ValueError('BINARY_CHECKSUM_MISMATCH')
        dest=ROOT/'external/pmix';dest.mkdir(parents=True,exist_ok=True)
        (dest/'pmix').write_bytes(binary);(dest/'pmix').chmod(0o755)
        (dest/'LICENSE.md').write_bytes(z.read('tools/pmix-0.16.1/LICENSE.md'))
        # Fixed manifest-defined paths, never ZipFile.extractall on user content.
        manifest=z.read('SHA256SUMS').decode()
        for line in manifest.splitlines():
            digest,name=line.split('  ',1)
            path=Path(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('INVALID_MANIFEST_PATH')
            data=z.read(name)
            if hashlib.sha256(data).hexdigest()!=digest:
                raise ValueError('RELEASE_MEMBER_CHECKSUM_MISMATCH')
            target=ROOT/'external/cad-experiment'/path
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        (ROOT/'external/cad-experiment/SHA256SUMS').write_text(manifest)
        (ROOT/'external/cad-experiment/tools/pmix-x86_64-unknown-linux-gnu/pmix').chmod(0o755)
    print('Verified pmix 0.16.1 and original experiment installed; no binary executed.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path)
    install(p.parse_args().archive)
