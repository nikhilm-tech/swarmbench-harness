#!/bin/bash
set -euo pipefail

cd /testbed

# Fetch and apply the gold solution from PR #14848.
# This only runs during oracle validation (-a oracle).
# The solution/ folder is NOT available to agents during normal runs.
curl -sL https://github.com/django/django/pull/14848.diff -o /tmp/pr14848.diff
git apply --whitespace=fix /tmp/pr14848.diff
