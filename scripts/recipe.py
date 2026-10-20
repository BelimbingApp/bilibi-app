#!/usr/bin/env python3
"""Materialize the setup; resolve only on pin, restore everywhere else."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(os.environ.get('BILIBI_BUILD_DIR', ROOT / 'build')).resolve()
PLATFORM = BUILD / 'platform'
TARGET = 'x86_64-unknown-linux-gnu'
GENERATED = {'Cargo.lock'} | {
    f'apps/{layer}/{name}' for layer in ('base', 'core', 'domains', 'extensions')
    for name in ('Cargo.toml', 'src/lib.rs')
}


def run(*args, cwd=PLATFORM, capture=False):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def read(path):
    with path.open('rb') as stream:
        return tomllib.load(stream)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def recipe():
    setup = read(ROOT / 'setup.toml')
    if set(setup) - {'format', 'targets', 'platform', 'domains', 'extensions'}:
        raise ValueError('Unknown setup.toml keys')
    if setup.get('format') != 1 or setup.get('targets') != [TARGET]:
        raise ValueError(f'Use format = 1 and targets = ["{TARGET}"]')
    sources = [('platform', setup['platform'])]
    for layer in ('domains', 'extensions'):
        seen = set()
        for source in setup.get(layer, []):
            name = source['id']
            if not re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*', name) or name in seen:
                raise ValueError(f'Invalid or duplicate {layer} id: {name}')
            seen.add(name)
            sources.append((f'apps/{layer}/{name}', source))
    for path, source in sources:
        expected = {'url', 'commit'} | ({'id'} if path != 'platform' else set())
        if set(source) != expected:
            raise ValueError(f'{path}: expected keys {sorted(expected)}')
        url = urlsplit(source['url'])
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.port or not url.path.endswith('.git')):
            raise ValueError(f'{path}: use an HTTPS Git URL without credentials, query or fragment')
        if not re.fullmatch('[0-9a-f]{40}', source['commit']):
            raise ValueError(f'{path}: commit must be a full lowercase 40-character commit ID')
    return setup, sources


def check_sources():
    _, sources = recipe()
    for path, source in sources:
        folder = PLATFORM if path == 'platform' else PLATFORM / path
        if folder.is_symlink() or Path(run('git', 'rev-parse', '--show-toplevel', cwd=folder, capture=True).strip()).resolve() != folder:
            raise ValueError(f'{path}: expected an independent checkout')
        if run('git', 'rev-parse', 'HEAD', cwd=folder, capture=True).strip() != source['commit']:
            raise ValueError(f'{path}: HEAD differs from setup.toml; use a fresh build folder')
        if run('git', 'remote', 'get-url', 'origin', cwd=folder, capture=True).strip() != source['url']:
            raise ValueError(f'{path}: origin differs from setup.toml')
        # Only the discover-modules outputs may differ in the Platform checkout.
        changes = run('git', 'status', '--porcelain', '--untracked-files=all', cwd=folder, capture=True)
        for line in changes.splitlines():
            if path != 'platform' or line[3:] not in GENERATED or line[:2] not in (' M', 'M '):
                raise ValueError(f'{path}: unexpected working tree change: {line}')
    expected = {path for path, _ in sources if path != 'platform'}
    actual = {str(folder.relative_to(PLATFORM))
              for layer in ('domains', 'extensions')
              for folder in (PLATFORM / 'apps' / layer).iterdir()
              if folder.is_dir() and not folder.name.startswith('.') and folder.name != 'src'}
    if actual != expected:
        raise ValueError(f'Mounted source set differs: expected {expected}, found {actual}')


def materialize():
    _, sources = recipe()
    BUILD.mkdir(parents=True, exist_ok=True)
    for path, source in sources:
        folder = PLATFORM if path == 'platform' else PLATFORM / path
        if not folder.exists():
            # --no-checkout avoids executing any source before the selected commit.
            run('git', 'clone', '--no-checkout', '--', source['url'], str(folder), cwd=BUILD)
            run('git', 'fetch', '--tags', 'origin', source['commit'], cwd=folder)
            run('git', 'checkout', '--detach', source['commit'], cwd=folder)
        # Fetch tags even for a previously materialized checkout. Pin/restore also
        # compares version labels, so a changed version tag cannot silently drift.
        run('git', 'fetch', '--tags', 'origin', cwd=folder)
    check_sources()


def check_pin():
    _, sources = recipe()
    pin = read(ROOT / 'composition/manifest.txt')
    if pin['platform'] != sources[0][1]['commit']:
        raise ValueError('The saved pin names another Platform commit; run pin after editing setup.toml')
    containers = {path.removeprefix('apps/'): source['commit'] for path, source in sources[1:]}
    if {name: item['head'] for name, item in pin.get('containers', {}).items()} != containers:
        raise ValueError('The saved pin names other Domains or Extensions; run pin')
    if digest(ROOT / 'composition/Cargo.lock') != pin['cargo_lock_sha256']:
        raise ValueError('The saved Cargo.lock does not match the pin')
    return pin


def restore():
    check_sources()
    pin = check_pin()
    target = PLATFORM / '.local/composition'
    target.mkdir(parents=True, exist_ok=True)
    for name in ('manifest.txt', 'Cargo.lock'):
        shutil.copyfile(ROOT / 'composition' / name, target / name)
    run('python3', 'scripts/discover-modules.py', '--restore')
    run('python3', 'scripts/discover-modules.py', '--check')
    # Compare all saved version tags with the tags actually fetched.
    module_spec = importlib.util.spec_from_file_location('discovery', PLATFORM / 'scripts/discover-modules.py')
    discovery = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(discovery)
    tag = pin.get('platform_tag')
    if discovery.version_at_head('Platform', PLATFORM) != (tag[1:] if tag else None):
        raise ValueError('Platform version tags changed since pinning')
    for name, item in pin.get('containers', {}).items():
        if discovery.version_at_head(name, PLATFORM / 'apps' / name) != item.get('version'):
            raise ValueError(f'{name}: version tags changed since pinning')
    check_sources()


def pin():
    check_sources()
    run('python3', 'scripts/discover-modules.py')
    run('bash', 'scripts/build-assets.sh', '--check')
    run('cargo', 'metadata', '--format-version', '1', capture=True)
    run('python3', 'scripts/discover-modules.py', '--pin')
    (ROOT / 'composition').mkdir(exist_ok=True)
    for name in ('manifest.txt', 'Cargo.lock'):
        shutil.copyfile(PLATFORM / '.local/composition' / name, ROOT / 'composition' / name)
    restore()


def checked_status(binary):
    pin = check_pin()
    status = run(str(binary.resolve()), 'status', capture=True)
    lines = status.splitlines()
    if len(lines) < 2 or lines[1] != 'Pin: .local/composition, compiled in at build time':
        raise ValueError('The built program has no valid compiled composition pin')
    expected = f'Bilibi {pin["platform_version"]}, '
    expected += f'release {pin["platform_tag"]}' if pin.get('platform_tag') else 'unreleased'
    expected += f', commit {pin["platform"]}'
    if lines[0] != expected:
        raise ValueError('Program Platform identity differs from the saved recipe')
    expected_lines = []
    for layer, heading in (('domains', 'Domains'), ('extensions', 'Extensions')):
        entries = [(name.split('/')[1], item) for name, item in pin.get('containers', {}).items() if name.startswith(layer + '/')]
        expected_lines.append(heading + (':' if entries else ': none mounted'))
        for name, item in sorted(entries):
            expected_lines.append(f'  {name} {item.get("version", "untagged")}, commit {item["head"]}, modules:')
    actual = lines[2:]
    if len(expected_lines) != len(actual) or any(
            not (got.startswith(want + ' ') if want.endswith('modules:') else got == want)
            for want, got in zip(expected_lines, actual)):
        raise ValueError('Program Domains or Extensions differ from the saved recipe')
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('materialize', 'pin', 'restore', 'verify', 'status'))
    parser.add_argument('--binary', type=Path)
    args = parser.parse_args()
    if args.command == 'status':
        print(checked_status(args.binary or Path(os.environ.get('CARGO_TARGET_DIR', BUILD / 'target')) / TARGET / 'release/bilibi-web'), end='')
    elif args.command == 'verify':
        check_sources()
        check_pin()
        run('python3', 'scripts/discover-modules.py', '--check')
        if digest(PLATFORM / 'Cargo.lock') != digest(ROOT / 'composition/Cargo.lock'):
            raise ValueError('The restored lock changed during validation')
    else:
        globals()[args.command]()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
