# Bilibi application starting point

This repository is what `./bilibi new <name>` copies when you keep an application of your own.

**New to Bilibi? Start in [bilibi](https://github.com/BelimbingApp/bilibi):**

```sh
git clone https://github.com/BelimbingApp/bilibi
cd bilibi && ./bilibi start
```

You can try Bilibi without creating a GitHub account or choosing a template. Later, `./bilibi new <name>` in that Platform clone creates your application repository.

## Run an existing application

Clone your application's repository, then run:

```sh
./bilibi start
```

The same command works with or without an AI agent. It obtains missing sources, installs commit safeguards, prepares missing prerequisites, and starts the existing development launcher. The launcher prints the address and development sign-in (`ai@agent.my` / `bilibi-dev`). Local HTTPS may need manual trust; the launcher keeps its loopback HTTP fallback.

Use apt-based Ubuntu or Debian, including WSL2, with Git, Bash, Python 3.11 or newer, network access and installation privileges. Setup may ask for your sudo password. Ubuntu 22.04 and Debian 11 ship older Python; install Python 3.11 or newer as `python3`, or use Ubuntu 24.04 or Debian 12. Setup prepares Rust, Node, PostgreSQL 18 and cargo-watch through the Platform's existing scripts. Release commands also need Docker with a running daemon and the pinned builder described below.

## Your workspace

```text
my-bilibi/                         # application Git repository
├── bilibi                         # common command entry point
├── setup.toml                     # URLs and exact component commits
├── composition/
│   ├── manifest.txt               # saved component identity
│   └── Cargo.lock                 # saved application dependency lock
├── scripts/
├── sources/                       # ignored, valuable editable clones
│   └── platform/                  # independent Platform Git repository
│       └── apps/
│           ├── domains/finance/   # independent Domain Git repository
│           └── extensions/        # optional independent Extension clones
├── build/                         # ignored outputs and caches
└── .local/                        # ignored workspace state
```

| Change | Repository to commit in |
| --- | --- |
| Application versions, manifest, lock, automation and documentation | Application root |
| Platform source and its unmounted generated composition | `sources/platform/` |
| Domain or Extension source | That component's own Git root |
| Build outputs, caches, keys, runtime data and local state | Never commit |

**Keep `sources/`: these are working repositories, not disposable build output.** Domains and Extensions remain ordinary nested clones at their existing Platform mount paths. They are neither submodules nor source symlinks. Older Platform launchers use an ignored `sources/platform/target` output link pointing into `build/target`; setup refuses to replace an existing target path.

`./bilibi status` shows every Git root, branch, local change and difference from the saved versions. Startup runs your local branches and edits. It does not update `setup.toml` or describe a stale saved pin as the running development version.

The Platform keeps its existing runtime locations: `.local/dev` contains development keys, `.local/postgres18` contains the private development database, and existing media and configuration paths remain unchanged. Environment variables retain their existing meaning. Workspace `.local/` contains command coordination and temporary pin candidates; runtime data is not moved there.

## Commands

| Command | What it does |
| --- | --- |
| `./bilibi start` | Obtain missing sources, prepare prerequisites and start local development with the development seed. |
| `./bilibi setup` | Prepare missing sources, safeguards and prerequisites; preserve existing branches, staged files, edits and untracked files. |
| `./bilibi add finance` | Install the Platform safeguard, then mount an official Domain or Extension from its catalogue. Existing destinations are preserved. |
| `./bilibi status` | Show application and component Git roots, branches, changes and saved-version differences. |
| `./bilibi pin` | Record committed component selections and resolved dependencies after validating a disposable candidate. |
| `./bilibi check` | Validate the saved commits and lock, format, lint, build, migrate, seed and boot against a separate empty database. |
| `./bilibi build` | Use the pinned builder to compile and verify the saved release composition with `--locked`. |

`./bilibi new` belongs to the Platform repository. In an application repository, you already own the application recipe.

Repeated setup does not fetch existing clones, so an unavailable remote cannot discard or block work already present. It never resets, cleans, switches or removes an existing checkout. A saved-version mismatch prints the path and next action. Strict checks and release builds instead require the saved commits and clean sources, except for recognised generated composition files.

## Save selected versions

Edit component source in its own repository, commit it and push it to its declared `origin`. Then run:

```sh
./bilibi pin
git diff -- setup.toml composition/
```

Pin reads the current Platform, Domain and Extension commits and origins, including components mounted by `add`. It refuses uncommitted edits outside recognised generated composition. It reconstructs a candidate from the declared HTTPS remotes without reusing local Git objects, checks assets, resolves dependencies in the pinned builder and validates the resulting pin and lock. Only then does it replace `setup.toml`, `composition/manifest.txt` and `composition/Cargo.lock`. A failed candidate leaves the previous saved set intact. Review and commit all three together.

Each source URL must use HTTPS without credentials and each commit must be a full lowercase 40-character ID. Domains and Extensions also need their declared `id`. Domains and Extensions are optional.

Checks restore the saved lock; they never resolve a new dependency set. They verify remote availability and saved version tags independently of your local objects. A local-only commit is insufficient for a release.

Run the combined gates with a **separate empty disposable PostgreSQL 18 database**:

```sh
export BILIBI_CHECK_DATABASE_URL=postgresql://YOUR-USER@127.0.0.1:5432/EMPTY-DISPOSABLE-DATABASE
./bilibi check
./bilibi build
```

`DATABASE_URL` remains your development connection and is never an implicit check target. Check refuses the same database or a database with existing tables or views. Check leaves its migrations and production seed in the disposable database; provide a new empty database on the next run. Docker uses host networking to reach it. Set `SETUP_CI_PORT` if the default check port, 38971, is occupied.

`BILIBI_SOURCE_DIR` overrides the source directory; `BILIBI_BUILD_DIR` still overrides outputs and caches. `CARGO_TARGET_DIR` overrides Cargo output. Use absolute paths outside editable sources for outputs. The builder maps all three consistently into its container. Pin candidates always use their own directories and ignore these overrides.

## Commit safeguards

Setup installs a repository-local Platform pre-commit hook that runs its own `scripts/discover-modules.py --check`. This rejects staged mounted composition and foreign path packages in the Platform lock. The application pre-commit hook validates the staged recipe, manifest and lock together; its application lock is allowed in Git. CI also validates the saved set because local hooks can be bypassed.

An existing executable pre-commit hook is preserved as `pre-commit.before-bilibi` in the same hook directory and runs first. Its failure stops the commit. Installation is repeatable. The guard finds its repository when it runs, so renaming or moving a checkout does not break it; an unmodified guard from an earlier release is replaced in place, while your own edits to an installed guard are left unchanged with a recovery message. It does not change `core.hooksPath` or global Git configuration. Tracked or symlink hooks, and hook directories outside this repository, are refused so setup cannot rewrite source files or shared hooks. For a shared hook path, configure a local hook directory (for example `git config --local core.hooksPath .git/hooks` in an ordinary clone), copy the hooks you want to retain there, inspect their relative-path assumptions, then rerun `./bilibi setup`. For a symlink hook, copy its target into that local directory as an ordinary executable first.

## Update an older application workspace

Keep the old checkout and runtime data until a parallel workspace has been used successfully. First record the old paths, remotes, branches, commits, staged and unstaged changes, untracked files, configuration and active processes. Inspect keys and database locations without printing secrets.

Create a separate application clone with the updated template commands and your reviewed recipe and composition. Run setup there. Validate with a separate database and local data paths. Transfer or commit source edits deliberately in their owning repositories; setup does not migrate the old `build/platform` clone. Do not delete the old `build/`: older layouts keep valuable sources there.

To adopt a clean existing clone manually, stop only that workspace's own processes by PID, verify the resolved source and destination paths, and move `build/platform` to an absent `sources/platform` on the same filesystem. Preserve its `.git`, nested component repositories, local files and runtime data together. Inspect an existing `target/` directory and deliberately move its outputs into `build/target` before setup creates its output link. Run status and setup, then validate with disposable data before changing editor or service paths. Roll back by restoring those recorded paths and the old application checkout; retain its database and keys.

Template updates are ordinary reviewed application changes: bring in the new wrapper, scripts and documentation on a branch while preserving your `setup.toml`, saved composition and application-specific automation. Resolve changes and run the saved-composition checks before merging. No update command overwrites your application automatically.

## Release your setup

**Build in development or GitHub Actions; servers install the finished release.** Before releasing, enable **release immutability** in your application repository's Settings. Protect `main` and the `setup-v*` tags so only release maintainers can change them, and allow GitHub Actions to run.

After the checks pass, tag the reviewed recipe commit:

```sh
git tag setup-v1.0.0
git push origin setup-v1.0.0
```

The setup version belongs to your repository. It is separate from the Platform and Domain versions. **Never move a published tag or replace a published asset.**

**Release setup** repeats the combined gates, checks the compiled program's reported composition, packages it, and creates a draft release. Only the draft job has `contents: write`. It uploads every asset and compares each digest with GitHub's recorded SHA-256. A rerun refuses an existing release instead of replacing its files.

Final publication also needs an authenticated GitHub CLI session and Node.js 20 or newer on your machine. Install the locked `gh-axi` helper:

```sh
npm ci --prefix scripts/github-tools --ignore-scripts --no-audit --no-fund
export PATH="$PWD/scripts/github-tools/node_modules/.bin:$PATH"
```

The owner publishes the verified draft as a separate final action. This keeps an administration credential out of Actions: checking GitHub's immutability setting requires administration read permission. Use your own authenticated `gh-axi` session, with that permission and permission to publish releases. In a clean checkout of the tagged commit, download all draft assets into an empty `dist/` folder:

```sh
git checkout setup-v1.0.0
gh-axi release download setup-v1.0.0 --repo YOUR-ORGANISATION/YOUR-SETUP --dir dist
python3 scripts/publish.py publish --tag setup-v1.0.0 --repository YOUR-ORGANISATION/YOUR-SETUP
```

The script checks the tagged commit, local checksums, GitHub asset digests and repository immutability before publishing. It then requires GitHub to report an immutable release. A `setup-vX.Y.Z-test` tag runs the same build but must stay a draft; delete the draft and tag after testing.

## Install a release

Download the `bilibi-setup-v1.0.0-x86_64-unknown-linux-gnu.tar.gz` asset from your own repository. Download `SHA256SUMS` too and verify the archive against GitHub's recorded asset digest or [release verification](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verify-release-integrity).

On the target Bilibi instance, open **Software → Releases**, upload that archive, review it, and confirm the install with a fresh 2FA code. Keep the same downloaded archive for Staging and Production. The existing installer handles backup, migration, switching, health checks, recovery and Undo.

GitHub's automatic **Source code** archives are not installable releases. The separate `bilibi-installer-x86_64-unknown-linux-gnu` and `bilibi-server-tools.tar.gz` assets are for initial server setup or deliberate administrator upgrades. Ordinary application installs do not update the shared installer.

An uploaded file remains operator supplied. Its checksum detects damaged bytes; **a checksum is not a signature or independent proof of who built it**. Use your configured repository over HTTPS, verify GitHub's digest, and test the exact archive on Staging before Production.

## Private sources

If a source is private, create a `SOURCE_READ_TOKEN` Actions secret with read access to only the required source repositories. The setup repository's normal token may not read another private repository.

The materialization and remote-verification step passes this secret through a password helper restricted to `https://github.com`. Unexpected hosts and prompts are refused. Sources on other hosts use your own host-specific credential helper. It saves no Git credentials and caches only Cargo downloads and build outputs. Pull requests receive no source token, so private-source checks must run on a trusted branch or tag. Never put a token in `setup.toml`, a Git URL, the lock, a cache or a release asset.

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

Archives have sorted entries, fixed modes, zero ownership, recipe-commit timestamps and no gzip timestamp. The workflow repackages the same program and compares every asset digest. This proves deterministic packaging. **The program is built from the recorded recipe; two clean compiler builds have not yet proved identical output bytes.** The workflow records the checked run time; compare a cold run with a later run that restores the cache. Cache keys include the source map, composition, toolchain and builder; cache hits still run every check.

## Where to go next

Read the Platform's [server installation guide](https://github.com/BelimbingApp/bilibi/blob/main/docs/server-install.md) for a fresh server and [Software guide](https://github.com/BelimbingApp/bilibi/blob/main/apps/base/software/README.md) for install and Undo. GitHub documents [immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases) and the [asset digest API](https://docs.github.com/en/rest/releases/assets).
