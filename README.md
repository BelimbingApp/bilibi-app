# Your Bilibi setup

This repository records your Bilibi Platform, Domains and Extensions, then builds a release you can upload to your servers.

The example includes the Platform and Finance Domain at exact commits. Your repository holds the recipe and dependency lock. The source checkouts and compiled programs stay in ignored build folders.

## Create your setup

Choose **Use this template → Create a new repository** on GitHub. Use one repository for each distinct setup. You can make yours public or private.

Before releasing, enable **release immutability** in your repository's Settings. Protect `main` and the `setup-v*` tags so only your release maintainers can change them. Allow GitHub Actions to run in the new repository.

Clone your repository on a development machine with Docker, Git and Python 3.11 or newer:

```sh
git clone https://github.com/YOUR-ORGANISATION/YOUR-SETUP.git
cd YOUR-SETUP
python3 scripts/recipe.py materialize
scripts/builder.sh python3 scripts/recipe.py restore
```

This downloads the recorded sources and restores the saved composition. It does not choose newer dependencies. **Build in development or GitHub Actions; servers install the finished release.**

## Change the Platform, Domains or Extensions

Edit `setup.toml`. Each source needs an HTTPS Git URL without credentials and a full 40-character commit ID. A Domain or Extension also needs its declared `id`, which determines its mount folder.

For example, the Finance source mounts at `build/platform/apps/domains/finance`. Extensions use `[[extensions]]` entries and mount at `build/platform/apps/extensions/<id>`. Each source remains an independent Git clone, with its tags fetched for version labels.

Move the previous build folder aside, then prepare the new recipe:

```sh
mv build build-previous
python3 scripts/recipe.py materialize
scripts/builder.sh python3 scripts/recipe.py pin
git diff -- setup.toml composition/
```

`pin` checks the assets, resolves dependencies, and uses the Platform's `discover-modules.py --pin` to save `composition/manifest.txt` and `composition/Cargo.lock`. Review and commit all three files together. Keep at least one real Domain or Extension until the Platform supports pinning an empty setup.

Open a pull request. **Check setup** restores the saved pin and lock, checks discovery, assets, formatting and Clippy, and builds every workspace member. It then migrates an empty PostgreSQL 18 database, applies production seeds, boots the app and requests `/`. It never runs an unlocked dependency resolution or rewrites the saved recipe.

You can run the same gates locally with an empty disposable PostgreSQL 18 database:

```sh
export DATABASE_URL=postgresql://YOUR-USER@127.0.0.1:5432/EMPTY-DISPOSABLE-DATABASE
scripts/builder.sh scripts/check.sh
```

The builder uses host networking to reach that database. Choose another `SETUP_CI_PORT` if its default application port, 38971, is occupied.

## Release your setup

After the checks pass, tag the reviewed recipe commit:

```sh
git tag setup-v1.0.0
git push origin setup-v1.0.0
```

The setup version belongs to your repository. It is separate from the Platform and Domain versions. **Never move a published tag or replace a published asset.**

**Release setup** repeats the combined gates, checks the compiled program's reported composition, packages it, and creates a draft release. Only the draft job has `contents: write`. It uploads every asset and compares each digest with GitHub's recorded SHA-256. A rerun refuses an existing release instead of replacing its files.

The owner publishes the verified draft as a separate final action. This keeps an administration credential out of Actions: checking GitHub's immutability setting requires administration read permission. Use your own authenticated `gh-axi` session, with that permission and permission to publish releases. In a clean checkout of the tagged commit, download all draft assets into an empty `dist/` folder:

```sh
git checkout setup-v1.0.0
gh-axi release download setup-v1.0.0 --repo YOUR-ORGANISATION/YOUR-SETUP --dir dist
python3 scripts/publish.py publish --tag setup-v1.0.0 --repository YOUR-ORGANISATION/YOUR-SETUP
```

The script checks the tagged commit, local checksums, GitHub asset digests and repository immutability before publishing. It then requires GitHub to report an immutable release. A `setup-vX.Y.Z-test` tag runs the same build but must stay a draft; delete the draft and tag after testing.

## Install a release

Download the `bilibi-setup-v1.0.0-x86_64-unknown-linux-gnu.tar.gz` asset from your own repository. Download `SHA256SUMS` too and verify the archive against GitHub's recorded asset digest or [release verification](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/verify-release-integrity).

On the target Bilibi instance, open **Software → Releases**, upload that archive, review it, and confirm the install with a fresh 2FA code. Keep the same downloaded archive for Staging and Production. The existing installer handles backup, migration, switching, health checks, recovery and Undo.

GitHub's automatic **Source code** archives are not installable releases. The separate `bilibi-installer-x86_64-unknown-linux-gnu` and `bilibi-server-tools.tar.gz` assets are for initial server setup or deliberate administrator upgrades. Ordinary application installs do not update the shared installer.

An uploaded file remains operator supplied. Its checksum detects damaged bytes; **a checksum is not a signature or independent proof of who built it**. Use your configured repository over HTTPS, verify GitHub's digest, and test the exact archive on Staging before Production.

## Private sources

If a source is private, create a `SOURCE_READ_TOKEN` Actions secret with read access to only the required source repositories. The setup repository's normal token may not read another private repository.

The materialization step passes this secret through a temporary password helper. It saves no Git credentials and caches only Cargo downloads and build outputs. Pull requests receive no source token, so private-source checks must run on a trusted branch or tag. Never put a token in `setup.toml`, a Git URL, the lock, a cache or a release asset.

For local private-source access, use your own Git credential helper or `GIT_ASKPASS`. No server credentials belong in Actions.

## What the release contains

| Asset | Purpose |
| --- | --- |
| `bilibi-setup-v<version>-x86_64-unknown-linux-gnu.tar.gz` | The existing upload format: root-level `bilibi-web`, `manifest.txt`, `Cargo.lock`, `release.json`, `bundle.json` and `SHA256SUMS`. |
| `bilibi-installer-x86_64-unknown-linux-gnu` | The matching installer, outside the app archive. |
| `bilibi-server-tools.tar.gz` | The matching server installation script, libraries, service templates and waiting page. |
| `recipe.json` | Setup repository, tag and commit; every source URL and commit; Platform, Domains, Extensions, toolchain, builder, target and dynamic dependencies. |
| `builder-packages.txt` | The builder's installed Debian package versions. |
| `publication.json` | The build run link and actual compiler and Node versions. |
| `SHA256SUMS` | SHA-256 for every other release asset. The app archive has a separate checksum list for its payload. |

`release.json` includes both `reference` and `commit` for containers because the existing upload preview and installer result use those different names. Extension identities are recorded and checked against the program; the current Platform upload preview does not display Extensions.

## Build requirements

Only Linux x86-64 (`x86_64-unknown-linux-gnu`) is supported by this template today. `rust-toolchain.toml` pins Rust 1.99.0. `builder.toml` pins the Rust and Node image digests, Node 24.6.0, PostgreSQL 18.0, the Debian package snapshot and the runner label. The Dockerfile uses that dated snapshot for Python and records installed packages.

The Debian 12 builder records its glibc version and the binary's dynamic dependencies in the recipe. This is a build baseline, not a claim that every Debian or Ubuntu release has been tested. Check the actual target server's libraries before promotion. Distributed programs do not use `target-cpu=native`.

Archives have sorted entries, fixed modes, zero ownership, recipe-commit timestamps and no gzip timestamp. The workflow repackages the same program and compares every asset digest. This proves deterministic packaging. **The program is built from the recorded recipe; two clean compiler builds have not yet proved identical output bytes.** Build logs record the checked run and a warm locked build separately. Cache keys include the source map, composition, toolchain and builder; cache hits still run every check.

## Where to go next

Read the Platform's [server installation guide](https://github.com/BelimbingApp/bilibi/blob/main/docs/server-install.md) for a fresh server and [Software guide](https://github.com/BelimbingApp/bilibi/blob/main/apps/base/software/README.md) for install and Undo. GitHub documents [immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases) and the [asset digest API](https://docs.github.com/en/rest/releases/assets).
