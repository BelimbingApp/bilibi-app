#!/usr/bin/env python3
"""Install repository-local, repeatable guards, chaining an existing pre-commit."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

MARKER = '# Bilibi repository guard v1'


def install(root, command):
    root = root.resolve()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    gitdir = Path(git('rev-parse', '--absolute-git-dir')).resolve()
    hooks = Path(git('rev-parse', '--git-path', 'hooks'))
    if not hooks.is_absolute():
        hooks = root / hooks
    hooks = hooks.resolve()
    # A configured shared hook directory cannot safely receive this checkout's guard.
    if not (hooks.is_relative_to(root) or hooks.is_relative_to(gitdir)):
        raise ValueError(f'{root}: core.hooksPath points outside this repository ({hooks}). Keep the shared hooks untouched; configure a repository-local hooks directory with your existing hooks copied there, then rerun ./bilibi setup. See README.md, Commit safeguards.')
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / 'pre-commit'
    previous = hooks / 'pre-commit.before-bilibi'
    if hook.is_symlink():
        raise ValueError(f'{hook}: symlink hook left unchanged; integrate the Bilibi guard in a repository-local hook (README.md)')
    text = ('#!/usr/bin/env bash\n' + MARKER + '\nset -euo pipefail\n'
            + f'cd -- {shlex.quote(str(root))}\n'
            + f'if [[ -x {shlex.quote(str(previous))} ]]; then {shlex.quote(str(previous))} "$@"; fi\n'
            + 'exec ' + shlex.join(command) + '\n')
    if hook.exists():
        current = hook.read_text()
        if current == text:
            if not os.access(hook, os.X_OK):
                raise ValueError(f'{hook}: guard is not executable; run chmod +x on this file, then ./bilibi setup.')
            return
        if hook.is_relative_to(root):
            tracked = subprocess.run(['git', '-C', str(root), 'ls-files', '--error-unmatch', str(hook.relative_to(root))],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if tracked.returncode == 0:
                raise ValueError(f'{hook}: tracked hook left unchanged. Use an untracked repository-local hooks directory and copy your custom hook there before ./bilibi setup (README.md).')
        if MARKER in current:
            raise ValueError(f'{hook}: installed guard has local edits; left unchanged. Reconcile them with pre-commit.before-bilibi before rerunning ./bilibi setup.')
        if previous.exists() or previous.is_symlink():
            raise ValueError(f'{previous}: hook backup already exists; reconcile the two hooks before ./bilibi setup')
        hook.rename(previous)
    with tempfile.NamedTemporaryFile(prefix='.bilibi-hook-', dir=hooks, mode='w', delete=False) as stream:
        stream.write(text)
        temporary = Path(stream.name)
    try:
        temporary.chmod(0o755)
        temporary.replace(hook)
    finally:
        temporary.unlink(missing_ok=True)
