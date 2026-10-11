#!/bin/bash
# Copy the CSR app's Documenso client here, unchanged (run on the Mac after csrapp/documenso.py changes).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cp "$HOME/HTE Apps/HTE-ServiceReports/csrapp/documenso.py" "$here/csrapp/documenso.py"
echo "copied; commit test/csrapp/documenso.py"
