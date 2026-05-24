#!/usr/bin/env bash
# Verify Linear and GitHub API credentials before any write operation.
# Returns exit 0 if both checks pass, exit 1 if either fails.
# Usage: check_auth.sh

set -euo pipefail

PASS=true

# --- Linear ---
if [ -z "${LINEAR_API_KEY:-}" ]; then
  echo "FAIL: LINEAR_API_KEY is not set"
  PASS=false
else
  RESP=$(curl -s -o /tmp/linear_auth_check.json -w "%{http_code}" \
    -X POST https://api.linear.app/graphql \
    -H "Authorization: $LINEAR_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"query": "{ viewer { name } }"}')
  if [ "$RESP" != "200" ]; then
    echo "FAIL: Linear auth check returned HTTP $RESP"
    cat /tmp/linear_auth_check.json 2>/dev/null || true
    PASS=false
  else
    echo "OK: Linear token valid"
  fi
fi

# --- GitHub ---
if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "FAIL: GITHUB_TOKEN is not set"
  PASS=false
else
  RESP=$(curl -s -o /tmp/github_auth_check.json -w "%{http_code}" \
    -H "Authorization: token $GITHUB_TOKEN" \
    "https://api.github.com/user")
  if [ "$RESP" != "200" ]; then
    echo "FAIL: GitHub token check returned HTTP $RESP"
    cat /tmp/github_auth_check.json 2>/dev/null || true
    PASS=false
  else
    echo "OK: GitHub token valid"
  fi
fi

if [ "$PASS" = true ]; then
  echo "All credentials OK"
  exit 0
else
  echo "One or more credential checks FAILED"
  exit 1
fi
