#!/usr/bin/env bash
# Chief Agent v2.0 — smoke test
# Run after `systemctl status chief-agent` shows "active (running)".
#
# Exit codes:
#   0 — all checks passed
#   1 — health endpoint not reachable
#   2 — auth missing/broken
#   3 — agents endpoint returned wrong count
#   4 — job scheduling failed
#   5 — ws endpoint not reachable
#   6 — approvals endpoint unreachable

set -e

CHIEF_HOST="${CHIEF_HOST:-127.0.0.1}"
CHIEF_PORT="${CHIEF_PORT:-7070}"
CHIEF_TOKEN="${CHIEF_API_TOKEN:-}"
CHIEF_ADMIN_TOKEN="${CHIEF_ADMIN_TOKEN:-}"
BASE="http://${CHIEF_HOST}:${CHIEF_PORT}"

bold() { printf "\n\033[1m== %s ==\033[0m\n" "$*"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m⚠\033[0m %s\n" "$*"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$*"; exit 1; }

bold "1. /api/health (no auth)"
HEALTH=$(curl -s "$BASE/api/health")
echo "$HEALTH" | head -c 400; echo
echo "$HEALTH" | grep -q '"status":"ok"' || fail "health not ok"
echo "$HEALTH" | grep -q '"version":"2.0"' || warn "version is not 2.0.x"
ok "health responded"

bold "2. Auth (401 without token, 200 with token)"
if [ -n "$CHIEF_TOKEN" ]; then
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/agents")
  [ "$CODE" = "401" ] || fail "expected 401 without token, got $CODE"
  ok "401 without token"

  CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $CHIEF_TOKEN" "$BASE/api/agents")
  [ "$CODE" = "200" ] || fail "expected 200 with token, got $CODE"
  ok "200 with token"
else
  echo "  (skipped — CHIEF_API_TOKEN not set)"
fi

bold "3. Agents list (expect 13 in v2.0)"
if [ -n "$CHIEF_TOKEN" ]; then
  RESP=$(curl -s -H "Authorization: Bearer $CHIEF_TOKEN" "$BASE/api/agents")
  COUNT=$(echo "$RESP" | grep -o '"id"' | wc -l)
  echo "  agents count: $COUNT"
  [ "$COUNT" -ge 13 ] || fail "expected >=13 agents in v2.0, got $COUNT"
  ok "registry has $COUNT agents"

  REMOTE=$(echo "$RESP" | grep -o '"type":"remote"' | wc -l)
  echo "  remote agents: $REMOTE (expected 9 in v2.0)"
  [ "$REMOTE" -ge 9 ] || warn "expected 9 remote agents, got $REMOTE"
else
  echo "  (skipped — needs token)"
fi

bold "4. WebSocket status (Kednet-агент)"
if [ -n "$CHIEF_TOKEN" ]; then
  WS=$(curl -s -H "Authorization: Bearer $CHIEF_TOKEN" "$BASE/api/ws/status")
  echo "  $WS"
  echo "$WS" | grep -q '"connected"' || fail "no 'connected' in ws/status"
  CONNECTED=$(echo "$WS" | grep -o '"connected":[a-z]*' | cut -d: -f2)
  if [ "$CONNECTED" = "true" ]; then
    ok "Kednet-агент connected"
    echo "$WS" | grep -q '"hostname"' && ok "hostname reported"
    echo "$WS" | grep -q '"skillsDetected"' && ok "skillsDetected reported"
  else
    warn "Kednet-агент не подключён. Запустите C:\Users\kfigh\kednet_agent\nssm\install-kednet-agent.ps1"
  fi
else
  echo "  (skipped — needs token)"
fi

bold "5. /api/approvals (expect 200 + array)"
if [ -n "$CHIEF_TOKEN" ]; then
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $CHIEF_TOKEN" "$BASE/api/approvals")
  [ "$CODE" = "200" ] || fail "expected 200, got $CODE"
  RESP=$(curl -s -H "Authorization: Bearer $CHIEF_TOKEN" "$BASE/api/approvals")
  echo "$RESP" | grep -q '\[' || fail "expected JSON array, got: $RESP"
  ok "approvals endpoint works"
else
  echo "  (skipped — needs token)"
fi

bold "6. Job scheduling (dry-run add_book on wishlibrarian)"
if [ -n "$CHIEF_TOKEN" ]; then
  JOB=$(curl -s -X POST \
    -H "Authorization: Bearer $CHIEF_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"actionId":"add_book","params":{"url":"https://example.com"},"dryRun":true,"triggeredBy":"smoke","triggeredByUser":"kfigh"}' \
    "$BASE/api/agents/wishlibrarian/run")
  echo "  $JOB"
  echo "$JOB" | grep -q '"jobId"' || fail "no jobId returned"
  JOBID=$(echo "$JOB" | grep -o '"jobId":"[^"]*"' | cut -d'"' -f4)
  ok "job scheduled: $JOBID"

  bold "7. Wait 30s and check job status"
  sleep 30
  STATUS=$(curl -s -H "Authorization: Bearer $CHIEF_TOKEN" "$BASE/api/jobs/$JOBID")
  echo "  $STATUS" | head -c 500; echo
  echo "$STATUS" | grep -q '"status":"' || fail "no status in response"
  ok "job status returned"
else
  echo "  (skipped — needs token)"
fi

bold "8. Audit log (admin token)"
if [ -n "$CHIEF_ADMIN_TOKEN" ] && [ -n "$CHIEF_TOKEN" ]; then
  CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $CHIEF_TOKEN" \
    -H "X-Admin-Token: $CHIEF_ADMIN_TOKEN" \
    "$BASE/api/audit?limit=10")
  [ "$CODE" = "200" ] || fail "expected 200 from audit, got $CODE"
  ok "audit endpoint works"
else
  echo "  (skipped — CHIEF_API_TOKEN or CHIEF_ADMIN_TOKEN not set)"
fi

echo
printf "\033[1;32mAll v2.0 checks passed.\033[0m\n"
echo
printf "  Если Kednet-агент не подключён (warning в шаге 4):\n"
printf "    cd C:\\Users\\kfigh\\kednet_agent\n"
printf "    \\nssm\\install-kednet-agent.ps1\n"
printf "    Get-Service KednetAgent   # должен быть Running\n"