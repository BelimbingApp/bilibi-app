#!/usr/bin/env bash
# Run a recipe command in the recorded builder, from a fixed build path.
set -euo pipefail
cd "$(dirname "$0")/.."
image="bilibi-setup-builder:$(sha256sum builder.toml scripts/Builder.Dockerfile | sha256sum | cut -c1-16)"
readarray -t config < <(python3 - <<'PY'
import tomllib
with open('builder.toml', 'rb') as stream:
    b = tomllib.load(stream)
for key in ('rust_image', 'node_image', 'debian_snapshot'):
    print(b[key])
PY
)
docker build --build-arg "RUST_IMAGE=${config[0]}" --build-arg "NODE_IMAGE=${config[1]}" \
  --build-arg "DEBIAN_SNAPSHOT=${config[2]}" -f scripts/Builder.Dockerfile -t "$image" .
readarray -t paths < <(python3 - <<'PY_PATHS'
import os
from pathlib import Path
root = Path.cwd()
print(Path(os.environ.get('BILIBI_SOURCE_DIR', root / 'sources')).resolve())
print(Path(os.environ.get('BILIBI_BUILD_DIR', root / 'build')).resolve())
print(Path(os.environ.get('CARGO_TARGET_DIR', Path(os.environ.get('BILIBI_BUILD_DIR', root / 'build')) / 'target')).resolve())
PY_PATHS
)
sources=${paths[0]}
outputs=${paths[1]}
target=${paths[2]}
mkdir -p "$sources" "$outputs/cargo/registry" "$outputs/cargo/git" "$target" "$outputs/npm-cache"
docker run --rm --network host --user "$(id -u):$(id -g)" \
  -v "$PWD:/workspace" \
  -v "$sources:/workspace/sources" \
  -v "$outputs:/workspace/build" \
  -v "$target:/workspace/build/target" \
  -v "$outputs/cargo/registry:/usr/local/cargo/registry" \
  -v "${outputs}/cargo/git:/usr/local/cargo/git" \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
  -e DATABASE_URL -e BILIBI_CHECK_DATABASE_URL -e SETUP_CI_PORT -e GITHUB_REPOSITORY -e GITHUB_SHA -e GITHUB_REF_NAME \
  -e GITHUB_RUN_ID -e GITHUB_SERVER_URL -e GITHUB_RUN_ATTEMPT \
  -e npm_config_cache=/workspace/build/npm-cache \
  -e BILIBI_SOURCE_DIR=/workspace/sources -e BILIBI_BUILD_DIR=/workspace/build \
  -e CARGO_TARGET_DIR=/workspace/build/target \
  -e 'RUSTFLAGS=--remap-path-prefix=/workspace=/bilibi --remap-path-prefix=/usr/local/cargo=/cargo' \
  "$image" "$@"
