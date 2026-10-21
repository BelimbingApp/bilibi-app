#!/bin/sh
# SOURCE_READ_TOKEN is scoped to github.com, never to arbitrary recipe hosts.
case "$1" in
  "Username for 'https://github.com': "*) printf '%s\n' x-access-token ;;
  "Password for 'https://x-access-token@github.com': "*) printf '%s\n' "$SOURCE_READ_TOKEN" ;;
  *) echo 'Refusing source credential request for an unexpected host or prompt' >&2; exit 1 ;;
esac
