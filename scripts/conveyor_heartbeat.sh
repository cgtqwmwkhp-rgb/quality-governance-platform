#!/usr/bin/env bash
# QGP conveyor heartbeat — advisory status for the merge bot.
# Policy: scripts/conveyor_policy.md
# Always exits 0 (advisory only).
set -u
REPO="${CONVEYOR_REPO:-cgtqwmwkhp-rgb/quality-governance-platform}"
STAGING_VERSION_URL="${STAGING_VERSION_URL:-https://qgp-staging-plantexpand.azurewebsites.net/api/v1/meta/version}"
# Priority mirrors scripts/conveyor_policy.md.
# Value P0s (#574/#575) MERGED — promote-tip handled via staging/main SHA below.
# Next open queue: hard Dependabot with code fix, then #355 human (do not auto-merge).
PRIORITY_PRS=(290 558 287 274 573 355)
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "CONVEYOR_STATUS {\"ts\":\"$TS\",\"repo\":\"$REPO\",\"phase\":\"start\"}"

STAGING_RAW="$(curl -sS --max-time 20 "$STAGING_VERSION_URL" 2>/dev/null || true)"
STAGING_JSON="$(echo "$STAGING_RAW" | python3 -c '
import sys,json,re
raw=sys.stdin.read().strip()
try:
  d=json.loads(raw)
  print(json.dumps(d if isinstance(d,dict) else {"raw":raw[:200]}))
except Exception:
  print(json.dumps({"error":"non_json","snippet":raw[:120]}))
' 2>/dev/null || echo '{}')"
STAGING_SHA="$(echo "$STAGING_JSON" | python3 -c 'import sys,json; d=json.load(sys.stdin); print((d.get("build_sha") or d.get("git_sha") or d.get("sha") or "unknown")[:12])' 2>/dev/null || echo unknown)"
echo "CONVEYOR_STATUS {\"ts\":\"$TS\",\"staging_sha\":\"$STAGING_SHA\",\"staging\":$STAGING_JSON}"

MAIN_SHA="$(gh api "repos/$REPO/commits/main" --jq '.sha[:12]' 2>/dev/null || echo unknown)"
echo "CONVEYOR_STATUS {\"ts\":\"$TS\",\"main_sha\":\"$MAIN_SHA\"}"

IN_FLIGHT="$(gh run list --repo "$REPO" --branch main --limit 10 --json databaseId,status,conclusion,name,headSha,url 2>/dev/null || echo '[]')"
echo "CONVEYOR_STATUS {\"ts\":\"$TS\",\"main_runs\":$IN_FLIGHT}"

LANE="$(echo "$IN_FLIGHT" | python3 -c '
import sys,json
runs=json.load(sys.stdin)
busy=[r for r in runs if r.get("status") in ("in_progress","queued")]
print("BUSY" if busy else "FREE")
for r in busy:
  print("IN_FLIGHT|%s|%s|%s" % (r.get("name") or "", (r.get("headSha") or "")[:12], r.get("url") or ""))
' 2>/dev/null || echo FREE)"
LANE_STATE="$(echo "$LANE" | head -1)"
echo "CONVEYOR_STATUS {\"ts\":\"$TS\",\"lane\":\"$LANE_STATE\"}"
echo "$LANE" | tail -n +2 | while IFS= read -r line; do
  echo "CONVEYOR_STATUS {\"ts\":\"$TS\",\"lane_detail\":\"$line\"}"
done

# All open PRs: mergeable + failing checks
OPEN_PRS="$(gh pr list --repo "$REPO" --state open --limit 100 \
  --json number,title,mergeable,headRefName,url,statusCheckRollup 2>/dev/null || echo '[]')"

echo "$OPEN_PRS" | python3 -c '
import sys,json
prs=json.load(sys.stdin)
priority={290,558,287,274,573,355}
def failing(pr):
  fails=[]
  for c in (pr.get("statusCheckRollup") or []):
    conc=c.get("conclusion") or ""
    st=c.get("state") or ""
    status=c.get("status") or ""
    if conc in ("FAILURE","TIMED_OUT","CANCELLED") or st=="FAILURE":
      fails.append(c.get("name") or "?")
    elif status and status not in ("COMPLETED","") and conc in ("", None) and st not in ("SUCCESS","NEUTRAL","SKIPPED"):
      pass  # pending — not failing
  return fails
print("OPEN_PR_COUNT %d" % len(prs))
# Priority first, then others by number ascending
ordered=sorted(prs, key=lambda p: (0 if p.get("number") in priority else 1, p.get("number") or 0))
for pr in ordered:
  n=pr.get("number")
  fails=failing(pr)
  pending=[c.get("name") for c in (pr.get("statusCheckRollup") or []) if (c.get("status") or "") not in ("COMPLETED","") and not (c.get("conclusion"))]
  flag="PRIORITY" if n in priority else "OTHER"
  print("PR #%s [%s] mergeable=%s failing=%s pending=%d title=%s url=%s" % (
    n, flag, pr.get("mergeable"), (",".join(fails) if fails else "none"), len(pending),
    (pr.get("title") or "")[:80], pr.get("url") or ""))
' 2>/dev/null | while IFS= read -r line; do
  echo "CONVEYOR_STATUS {\"ts\":\"$TS\",\"prs\":\"$line\"}"
done

# NEXT_ACTION from priority queue
NEXT=""
for n in "${PRIORITY_PRS[@]}"; do
  STATE="$(gh pr view "$n" --repo "$REPO" --json state,mergeable,title,url,statusCheckRollup 2>/dev/null || echo '')"
  [[ -z "$STATE" ]] && continue
  eval "$(echo "$STATE" | python3 -c '
import sys,json
d=json.load(sys.stdin)
fails=[c.get("name") for c in (d.get("statusCheckRollup") or []) if c.get("conclusion") in ("FAILURE","TIMED_OUT","CANCELLED") or c.get("state")=="FAILURE"]
pending=[c.get("name") for c in (d.get("statusCheckRollup") or []) if (c.get("status") or "") not in ("COMPLETED","") and not c.get("conclusion")]
print("PR_STATE=%r" % (d.get("state") or ""))
print("MERGEABLE=%r" % (d.get("mergeable") or ""))
print("FAILING=%r" % ",".join(fails))
print("PENDING=%r" % len(pending))
' 2>/dev/null || true)"
  if [[ "${PR_STATE:-}" == "OPEN" && -z "$NEXT" ]]; then
    if [[ -n "${FAILING:-}" ]]; then
      NEXT="FIX #$n (failing: $FAILING) — push fix to PR branch; do not merge"
    elif [[ "${PENDING:-0}" != "0" ]]; then
      NEXT="WAIT #$n checks ($PENDING pending) — lane=$LANE_STATE"
    elif [[ "$MERGEABLE" != "MERGEABLE" ]]; then
      NEXT="UPDATE #$n onto main (mergeable=$MERGEABLE)"
    elif [[ "$LANE_STATE" != "FREE" ]]; then
      NEXT="HOLD #$n green but lane BUSY — wait for main CI/deploy"
    else
      NEXT="MERGE #$n squash when required checks green (lane FREE)"
    fi
  fi
done

if [[ -z "$NEXT" ]]; then
  if [[ "$STAGING_SHA" == "unknown" ]]; then
    NEXT="STAGING DOWN/ERROR — diagnose Azure staging before further merges; do not prod promote"
  elif [[ "$MAIN_SHA" != "unknown" && "$STAGING_SHA" != "$MAIN_SHA" ]]; then
    NEXT="WAIT staging cutover (live=$STAGING_SHA main=$MAIN_SHA) before next merge"
  else
    NEXT="QUEUE clear / staging~main — prepare release_signoff; no prod without Redis/Celery KV confirmation"
  fi
fi

echo "NEXT_ACTION $NEXT"
echo "CONVEYOR_NEXT_ACTION $NEXT"
echo "CONVEYOR_STATUS {\"ts\":\"$TS\",\"phase\":\"done\",\"next\":\"$NEXT\",\"main_sha\":\"$MAIN_SHA\",\"staging_sha\":\"$STAGING_SHA\",\"lane\":\"$LANE_STATE\"}"
exit 0
