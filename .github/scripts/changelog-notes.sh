#!/bin/sh
# Print the docs/changelog/index.rst section for a version, for use as release
# notes. Fails when that version has no section or an empty one. Run from the
# repository root.
set -eu

version=${1:?usage: changelog-notes.sh VERSION}
version=${version#v}

notes=$(awk -v heading="Version $version" '
  $0 == heading { found = 1; getline; next }
  found && /^Version / { exit }
  found { gsub(/:code:/, ""); print }
' docs/changelog/index.rst)

printf '%s\n' "$notes" | grep -q '[^[:space:]]' || {
  echo "docs/changelog/index.rst has no notes for version $version" >&2
  exit 1
}

printf '%s\n' "$notes"
