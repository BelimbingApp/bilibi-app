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
mkdir -p build/cargo/registry build/cargo/git build/target build/npm-cache
docker run --rm --network host --user "$(id -u):$(id -g)" \
  -v "$PWD:/workspace" \
  -v "$PWD/build/cargo/registry:/usr/local/cargo/registry" \
  -v "$PWD/build/cargo/git:/usr/local/cargo/git" \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
  -e DATABASE_URL -e SETUP_CI_PORT -e GITHUB_REPOSITORY -e GITHUB_SHA -e GITHUB_REF_NAME \
  -e GITHUB_RUN_ID -e GITHUB_SERVER_URL -e GITHUB_RUN_ATTEMPT \
  -e npm_config_cache=/workspace/build/npm-cache \
  -e CARGO_TARGET_DIR=/workspace/build/target \
  -e 'RUSTFLAGS=--remap-path-prefix=/workspace=/bilibi --remap-path-prefix=/usr/local/cargo=/cargo' \
  "$image" "$@"
