#!/usr/bin/env python3
"""Application workspace commands; component repositories own their local work."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

import recipe

ROOT, PLATFORM, BUILD = recipe.ROOT, recipe.PLATFORM, recipe.BUILD


def run(*args, cwd=ROOT, capture=False):
    return recipe.run(*map(str, args), cwd=cwd, capture=capture)


def repositories():
    yield 'platform', PLATFORM
    if PLATFORM.is_dir():
        for layer in ('domains', 'extensions'):
            parent = PLATFORM / 'apps' / layer
            if parent.is_dir():
                for folder in sorted(parent.iterdir()):
                    if folder.is_dir() and folder.name != 'src' and not folder.name.startswith('.'):
                        yield f'apps/{layer}/{folder.name}', folder


def status():
    _, sources = recipe.recipe()
    saved = dict(sources)
    print(f'Application: {ROOT}')
    print(run('git', 'status', '--short', '--branch', capture=True), end='')
    found = set()
    for name, folder in repositories():
        found.add(name)
        print(f'\n{name}: {folder}')
        if not folder.exists():
            print('Missing; run ./bilibi setup.')
            continue
        recipe.checkout(folder)
        head = run('git', 'rev-parse', 'HEAD', cwd=folder, capture=True).strip()
        print(run('git', 'status', '--short', '--branch', cwd=folder, capture=True), end='')
        print(f'Commit: {head}')
        origin = run('git', 'remote', 'get-url', 'origin', cwd=folder, capture=True).strip()
        entry = saved.get(name)
        if entry is None:
            print('Not saved in setup.toml; commit and push, then run ./bilibi pin.')
        elif head != entry['commit'] or origin != entry['url']:
            print(f'Saved: {entry["commit"]} from {entry["url"]}. Commit and push local changes, then ./bilibi pin to save them.')
        else:
            print('Matches saved source revision (working changes shown above).')
    for name in saved.keys() - found:
        print(f'\n{name}: {PLATFORM / name} — missing; run ./bilibi setup.')


def hooks():
    spec = importlib.util.spec_from_file_location('hooks', ROOT / 'scripts/install-hooks.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.install(PLATFORM, ['python3', str(PLATFORM / 'scripts/discover-modules.py'), '--check'])
    module.install(ROOT, ['python3', str(ROOT / 'scripts/workspace.py'), 'check-staged'])


def output_paths():
    BUILD.mkdir(parents=True, exist_ok=True)
    target = Path(os.environ.get('CARGO_TARGET_DIR', BUILD / 'target')).resolve()
    if target.is_relative_to(recipe.SOURCES):
        raise ValueError('CARGO_TARGET_DIR must be outside sources/; use build/target for outputs')
    target.mkdir(parents=True, exist_ok=True)
    # A symlink does not match Platform's directory-only /target/ ignore.
    # Keep this machine-local output link ignored without changing component source.
    exclude = Path(run('git', 'rev-parse', '--git-path', 'info/exclude', cwd=PLATFORM, capture=True).strip())
    if not exclude.is_absolute():
        exclude = PLATFORM / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text() if exclude.exists() else ''
    if '/target' not in existing.splitlines():
        with exclude.open('a') as stream:
            stream.write('\n# Bilibi workspace output link\n/target\n')
    # Older supported Platform launchers address target/debug directly. This is
    # an output link only: no editable source repository is mounted by symlink.
    link = PLATFORM / 'target'
    if link.is_symlink() and link.resolve() == target:
        pass
    elif link.exists() or link.is_symlink():
        raise ValueError(f'{link}: existing output path left unchanged. Move it to {target} deliberately, then remove the old path and rerun ./bilibi setup.')
    else:
        link.symlink_to(target, target_is_directory=True)
    os.environ['CARGO_TARGET_DIR'] = str(target)


def setup():
    for tool in ('git', 'bash'):
        if not shutil.which(tool):
            raise ValueError(f'Install {tool}, then rerun ./bilibi setup.')
    recipe.materialize()
    hooks()
    output_paths()
    run('bash', ROOT / 'scripts/dev-setup.sh', PLATFORM)
    print('Setup complete. Local sources and runtime data are preserved. Run ./bilibi start.')


def start():
    setup()
    status()
    print('\nStarting local sources with the development seed. Saved release pins are not the identity of this development run.', flush=True)
    # A development run must not compile a stale release pin as its identity.
    # Keep the old machine-local pin for inspection rather than deleting it.
    pin = PLATFORM / '.local/composition'
    if (pin / 'manifest.txt').exists():
        backup = PLATFORM / '.local' / ('composition-before-development-' + uuid.uuid4().hex)
        pin.rename(backup)
    os.chdir(PLATFORM)
    os.execvp('bash', ['bash', '-c', 'if [[ -f $HOME/.cargo/env ]]; then source "$HOME/.cargo/env"; fi; exec bash scripts/start-app.sh'])


def add(component):
    if not re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*', component):
        raise ValueError('Use a component ID such as finance or supply_chain.')
    # Obtain missing sources and install the guard even before the first start.
    recipe.materialize()
    hooks()
    catalogue = json.loads((PLATFORM / 'catalogue.json').read_text())
    matches = [(layer, facts) for layer in ('domains', 'extensions')
               if (facts := catalogue.get(layer, {}).get(component)) is not None]
    if len(matches) != 1:
        raise ValueError(f'{component}: choose an unambiguous official Domain or Extension from the Software page')
    layer, facts = matches[0]
    url = facts['repository'].removesuffix('.git') + '.git'
    if not re.fullmatch(r'https://github\.com/BelimbingApp/[A-Za-z0-9_.-]+\.git', url):
        raise ValueError(f'{component}: the catalogue entry is not an official BelimbingApp repository')
    folder = PLATFORM / 'apps' / layer / component
    if folder.exists() or folder.is_symlink():
        raise ValueError(f'{folder}: already exists; local work left unchanged. Run ./bilibi status.')
    # Select the remote's default branch; pin will later record this exact commit.
    listing = run('git', 'ls-remote', url, 'HEAD', capture=True).split()
    if not listing:
        raise ValueError(f'{component}: remote has no HEAD')
    recipe.clone({'url': url, 'commit': listing[0]}, folder)
    print(f'Added {component} at {folder}. Run ./bilibi start. Commit and push component edits before ./bilibi pin.')


def selected_recipe():
    setup, _ = recipe.recipe()
    selected = {'format': 1, 'targets': setup['targets'], 'domains': [], 'extensions': []}
    for name, folder in repositories():
        recipe.checkout(folder)
        changes = run('git', 'status', '--porcelain', '--untracked-files=all', cwd=folder, capture=True)
        for line in changes.splitlines():
            if name != 'platform' or line[3:] not in recipe.GENERATED or line[:2] not in (' M', 'M '):
                raise ValueError(f'{folder}: commit local changes in this repository and push before ./bilibi pin ({line})')
        source = {'url': run('git', 'remote', 'get-url', 'origin', cwd=folder, capture=True).strip(),
                  'commit': run('git', 'rev-parse', 'HEAD', cwd=folder, capture=True).strip()}
        if name == 'platform':
            selected['platform'] = source
        else:
            _, layer, identity = name.split('/')
            selected[layer].append({'id': identity, **source})
    return selected


def serialize(setup):
    # JSON strings are also TOML basic strings for validated source URLs and IDs.
    lines = ['format = 1', 'targets = ' + json.dumps(setup['targets']), '', '[platform]']
    for key, value in setup['platform'].items():
        lines.append(f'{key} = {json.dumps(value)}')
    for layer in ('domains', 'extensions'):
        for source in setup[layer]:
            lines.extend(['', f'[[{layer}]]'])
            lines.extend(f'{key} = {json.dumps(value)}' for key, value in source.items())
    return '\n'.join(lines) + '\n'


def pin():
    selected = selected_recipe()
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    before = {name: (ROOT / name).read_bytes() for name in ('setup.toml', 'composition/manifest.txt', 'composition/Cargo.lock')}
    with tempfile.TemporaryDirectory(prefix='pin-candidate-', dir=local) as temp:
        candidate = Path(temp)
        for name in ('scripts', 'composition'):
            shutil.copytree(ROOT / name, candidate / name, ignore=shutil.ignore_patterns('__pycache__', 'node_modules'))
        for name in ('builder.toml', 'rust-toolchain.toml', '.dockerignore'):
            shutil.copyfile(ROOT / name, candidate / name)
        (candidate / 'setup.toml').write_text(serialize(selected))
        recipe.recipe(candidate)  # Validate every URL, commit and component ID first.
        env = dict(os.environ)
        # Never let a caller's path override make this candidate touch live sources.
        for key in ('BILIBI_SOURCE_DIR', 'BILIBI_BUILD_DIR', 'CARGO_TARGET_DIR'):
            env.pop(key, None)
        subprocess.run(['python3', str(candidate / 'scripts/recipe.py'), 'materialize'], env=env, check=True)
        subprocess.run(['bash', str(candidate / 'scripts/builder.sh'), 'python3', 'scripts/recipe.py', 'pin-candidate'], env=env, check=True)
        recipe.check_pin(candidate)
        if selected_recipe() != selected:
            raise ValueError('Local source selections changed while preparing the candidate; saved set left unchanged. Rerun ./bilibi pin.')
        # Concurrent hand edits must never be overwritten by the prepared candidate.
        if any((ROOT / name).read_bytes() != data for name, data in before.items()):
            raise ValueError('Saved recipe changed while pin was preparing; candidate discarded. Rerun ./bilibi pin.')
        try:
            for name in before:
                replacement = ROOT / name
                with tempfile.NamedTemporaryFile(prefix='.bilibi-pin-', dir=replacement.parent, delete=False) as stream:
                    pending = Path(stream.name)
                    stream.write((candidate / name).read_bytes())
                try:
                    pending.chmod(replacement.stat().st_mode & 0o777)
                    pending.replace(replacement)
                finally:
                    pending.unlink(missing_ok=True)
        except BaseException:
            for name, data in before.items():
                (ROOT / name).write_bytes(data)
            raise
    print('Saved the validated candidate. Review and commit setup.toml and composition/ together. Run ./bilibi setup in a fresh clone, then ./bilibi check.')


def check_staged():
    with tempfile.TemporaryDirectory(prefix='bilibi-index-') as temp:
        index = Path(temp)
        (index / 'composition').mkdir()
        for name in ('setup.toml', 'composition/manifest.txt', 'composition/Cargo.lock'):
            (index / name).write_text(run('git', 'show', ':' + name, capture=True))
        recipe.check_pin(index)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('start', 'add', 'status', 'setup', 'check', 'pin', 'build', 'check-staged'),
                        metavar='{start,add,status,setup,check,pin,build}')
    parser.add_argument('component', nargs='?')
    args = parser.parse_args()
    if (args.command == 'add') != (args.component is not None):
        parser.error('Use ./bilibi add <component>; other commands take no arguments')
    if args.command == 'status':
        status()
        return
    if args.command == 'check-staged':
        check_staged()
        return
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    with (local / 'workspace.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == 'add':
            add(args.component)
        elif args.command in ('check', 'build'):
            recipe.check_sources()
            recipe.check_pin()
            recipe.verify_remote()
            run('bash', ROOT / 'scripts/builder.sh', 'scripts/check.sh' if args.command == 'check' else 'scripts/build.sh')
        else:
            globals()[args.command]()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
