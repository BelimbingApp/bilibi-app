ARG NODE_IMAGE
ARG RUST_IMAGE
FROM ${NODE_IMAGE} AS node
FROM ${RUST_IMAGE}
ARG DEBIAN_SNAPSHOT
# All Debian dependencies come from one dated package index. No moving apt mirror.
RUN rm -f /etc/apt/sources.list.d/* && \
    printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/%s bookworm main\n' "$DEBIAN_SNAPSHOT" > /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends python3 && \
    rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx && \
    rustup component add --toolchain 1.99.0 rustfmt clippy && \
    dpkg-query -W > /builder-packages.txt
ENV CARGO_BUILD_JOBS=2 CARGO_PROFILE_RELEASE_STRIP=symbols CARGO_INCREMENTAL=0
WORKDIR /workspace
