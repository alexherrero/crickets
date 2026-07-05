#!/usr/bin/env bash
# check-no-pii.sh — thin repo-root shim.
#
# The canonical copy lives at src/pii/scripts/check-no-pii.sh (the group
# source that ships inside the `pii` plugin's own payload — R2.4 task 7;
# it previously lived only here, outside any plugin's source tree, so an
# install elsewhere never got the detector). Kept here, delegating, so
# every existing caller (check-all.sh, tests-linux.yml, an installed
# pre-push hook, pii-scrubber's sibling-checkout fallback) keeps working
# by the same path with no changes.
set -euo pipefail
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../src/pii/scripts/check-no-pii.sh" "$@"
