#!/bin/sh
# Regenerate the vectors with Python, require the Go toolchain to recompute
# every value identically, and only then install the JSON files.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
out=$(dirname "$here")
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
python3 "$here/agora_tv.py" generate "$stage"
(cd "$here/go" && go run . check "$stage")
python3 "$here/agora_tv.py" check "$stage"
cp "$stage"/*.json "$out"/
echo "installed vectors in $out"
