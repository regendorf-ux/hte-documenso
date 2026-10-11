#!/bin/bash
# Re-make patches/ and overlay/ from a working Documenso clone whose branch "hte" holds HTE's changes on
# top of the tag in UPSTREAM:  tools/make-patch.sh ~/Sites/hte-documenso
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
tag="$(cat "$here/UPSTREAM")"
cd "$1"
git diff "$tag" hte -- . ':(exclude)apps/remix/public' > "$here/patches/hte.patch"
rm -rf "$here/overlay"
git diff --name-only "$tag" hte -- apps/remix/public | while read -r f; do
  mkdir -p "$here/overlay/$(dirname "$f")"
  git show "hte:$f" > "$here/overlay/$f"
done
echo "patches/ and overlay/ re-made from $1 (hte vs $tag)"
