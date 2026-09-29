"""Fail if media source or asset fingerprints disagree with the checkout."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(folder, root):
    manifest=json.loads((folder/'manifest.json').read_text())
    for key,base in [('source_sha256',root),('assets_sha256',folder)]:
        entries=manifest['provenance'][key] if key=='source_sha256' else manifest[key]
        for name, expected in entries.items():
            path=base/name
            actual=hashlib.sha256(path.read_bytes()).hexdigest()
            if actual!=expected:raise ValueError(f'Fingerprint mismatch: {name}')
    print('Source and asset fingerprints match.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=Path('media'))
    args=p.parse_args()
    verify(args.directory,Path(__file__).resolve().parents[1])
