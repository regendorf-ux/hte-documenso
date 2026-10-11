#!/bin/bash
# Put HTE's changes on a checkout of Documenso:  tools/apply.sh <documenso checkout>
# patches/*.patch are the code changes; overlay/ holds the files that are only added or replaced
# (HTE's logo, photo, fonts and tab icons). Fails, changing nothing, if a patch no longer applies.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
src="$(cd "$1" && pwd)"
cd "$src"
git apply --check --whitespace=nowarn "$here"/patches/*.patch
git apply --whitespace=nowarn "$here"/patches/*.patch
cp -R "$here/overlay/." "$src/"
echo "HTE changes applied to $src"
