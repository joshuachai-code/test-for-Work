"""Save one verified deliverable to the assigned task's OneDrive review folder."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

DEFAULT_ROOT = Path.home() / 'Library/CloudStorage/OneDrive-Personal/Boardroom'


def digest(path):
    with path.open('rb') as stream:
        sha = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(block)
        return sha.hexdigest()


def deliver(source, task_id, root=None):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}', task_id):
        raise ValueError('Use the exact Cosec Desk task ID.')
    source = Path(source)
    if not source.is_file() or not source.stat().st_size:
        raise ValueError('The completed file is missing or empty.')
    root = Path(root or os.environ.get('BOARDROOM_DATA_ROOT', DEFAULT_ROOT)).resolve(strict=True)
    folder = root / 'Completed Forms' / task_id
    if folder.resolve() != folder or any(ord(c) < 32 for c in source.name):
        raise ValueError('Unexpected delivery path.')
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / source.name
    if target.is_symlink():
        raise ValueError('Destination must be a regular file.')
    expected = digest(source)
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=folder, prefix='.review-', delete=False) as tmp:
            temp = Path(tmp.name)
        try:
            shutil.copyfile(source, temp)
            if digest(temp) != expected:
                raise ValueError('Source changed during delivery.')
            try:
                os.link(temp, target)
            except FileExistsError:
                pass
        finally:
            temp.unlink(missing_ok=True)
    if target.is_symlink() or digest(target) != expected:
        raise ValueError('A different file already exists. Preserve it and use a versioned filename.')
    return {'review_file':target.relative_to(root).as_posix(), 'sha256':expected, 'cloud_sync':'unverified'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id')
    parser.add_argument('file')
    args = parser.parse_args()
    try:
        print(json.dumps(deliver(args.file, args.task_id)))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
