#!/usr/bin/env bash
# The combined Domain gates, restoring the committed recipe without resolving it.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd -P)
: "${DATABASE_URL:?Use an empty disposable PostgreSQL 18 database}"
export CARGO_TARGET_DIR=${CARGO_TARGET_DIR:-$root/build/target}
target=x86_64-unknown-linux-gnu
python3 "$root/scripts/recipe.py" restore
cd "$root/build/platform"
npm ci --prefix apps/base/ui/assets --no-audit --no-fund
./scripts/build-assets.sh --check
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --target "$target" --locked -- -D warnings
cargo build --workspace --release --target "$target" --locked
python3 "$root/scripts/recipe.py" verify
app="$CARGO_TARGET_DIR/$target/release/bilibi-web"
python3 "$root/scripts/recipe.py" status --binary "$app"
"$app" migrate
"$app" seed-production
port=${SETUP_CI_PORT:-38971}
BIND_ADDR="127.0.0.1:$port" APP_ORIGIN="http://127.0.0.1:$port" "$app" run &
server=$!
trap 'kill "$server" 2>/dev/null || true; wait "$server" 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do
    kill -0 "$server" 2>/dev/null || { echo 'App exited during boot' >&2; exit 1; }
    status=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/" || true)
    if [[ $status =~ ^(200|30[1-8])$ ]]; then
        echo "GET / answered $status"
        exit 0
    fi
    sleep 1
done
echo 'GET / did not become ready' >&2
exit 1
