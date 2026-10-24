#!/usr/bin/env bash
# End-to-end check of a running deployment through its public entry point:
# health, the exact version being served, and the full user journey.
#
#   scripts/smoke-test.sh [expected-git-sha]
source "$(dirname "$0")/lib.sh"
need curl python3
EXPECTED_SHA="${1:-}"
ensure_base_url

log "smoke test against $BASE_URL"
curl -fsS "$BASE_URL/healthz" >/dev/null && ok "liveness /healthz"
curl -fsS "$BASE_URL/readyz" | grep -q '"database":"up"' && ok "readiness /readyz (database up)"

version_json="$(curl -fsS "$BASE_URL/version")"
echo "  version: $version_json"
if [[ -n "$EXPECTED_SHA" ]]; then
  served="$(python3 -c 'import json,sys;print(json.load(sys.stdin)["git_sha"])' <<<"$version_json")"
  [[ "$served" == "$EXPECTED_SHA" ]] && ok "serving expected commit $EXPECTED_SHA" \
    || fail "serving $served, expected $EXPECTED_SHA"
fi

curl -fsS "$BASE_URL/" | grep -q "<title>Shortener</title>" && ok "web UI served"

# User journey: shorten a URL, follow it, see the click counted, clean up.
code="smoke$(date +%s)"
target="https://example.com/smoke/$code"
curl -fsS -X POST "$BASE_URL/api/links" -H 'Content-Type: application/json' \
  -d "{\"url\":\"$target\",\"code\":\"$code\"}" >/dev/null && ok "created /$code"
loc="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "$BASE_URL/$code")"
[[ "$loc" == "302 $target" ]] && ok "/$code redirects (302) to $target" || fail "redirect returned: $loc"
curl -fsS "$BASE_URL/api/links/$code" | grep -q '"clicks":1' && ok "click counted"
curl -fsS "$BASE_URL/api/links" | grep -q "\"$code\"" && ok "/$code listed"
http() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
c="$(http -X POST "$BASE_URL/api/links" -H 'Content-Type: application/json' -d "{\"url\":\"https://a.example\",\"code\":\"$code\"}")"
[[ "$c" == "409" ]] && ok "duplicate code rejected (409)" || fail "duplicate code returned $c"
c="$(http -X POST "$BASE_URL/api/links" -H 'Content-Type: application/json' -d '{"url":"not-a-url"}')"
[[ "$c" == "422" ]] && ok "invalid URL rejected (422)" || fail "validation returned $c"
c="$(http -X DELETE "$BASE_URL/api/links/$code")"
[[ "$c" == "204" ]] && ok "/$code deleted" || fail "delete returned $c"
c="$(http "$BASE_URL/$code")"
[[ "$c" == "404" ]] && ok "deleted code now 404" || fail "deleted code returned $c"

curl -fsS "$BASE_URL/metrics" | grep -q 'links_operations_total{operation="redirect",outcome="success"}' \
  && ok "metrics exported"
log "smoke test passed"
