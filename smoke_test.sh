#!/usr/bin/env bash
# CiXiS end-to-end smoke test.
# Boots the local backend (:8000) and the remote QR server (:9000), then drives a
# full real-world flow over HTTP and asserts each step. Prints PASS/FAIL and exits
# non-zero on failure. Tears down both servers on exit.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BACK_PY="$ROOT/backend/.venv/bin/python"
REM_PY="$ROOT/remote/.venv/bin/python"

# Use a throwaway backend SQLite so the test never disturbs real dev data
# (the real DB may already have today's day-closing).
export CIXIS_DB_PATH="$ROOT/backend/smoke.sqlite3"
BACK_DB="$CIXIS_DB_PATH"
rm -f "$BACK_DB"

cleanup() {
  [ -n "${BACK_PID:-}" ] && kill "$BACK_PID" 2>/dev/null
  [ -n "${REM_PID:-}" ]  && kill "$REM_PID" 2>/dev/null
  rm -f "$BACK_DB"
}
trap cleanup EXIT

echo "== preparing databases =="
( cd "$ROOT/backend" && "$BACK_PY" manage.py migrate --noinput >/dev/null \
  && "$BACK_PY" manage.py init_settings >/dev/null \
  && "$BACK_PY" manage.py seed_menu >/dev/null )
( cd "$ROOT/remote" && CIXIS_API_KEY=dev-cixis-key "$REM_PY" manage.py migrate --noinput >/dev/null )

echo "== starting servers =="
( cd "$ROOT/remote"  && CIXIS_API_KEY=dev-cixis-key "$REM_PY"  manage.py runserver 127.0.0.1:9000 --noreload >/tmp/cixis-smoke-remote.log 2>&1 ) & REM_PID=$!
( cd "$ROOT/backend" && CIXIS_DB_PATH="$BACK_DB" "$BACK_PY" manage.py runserver 127.0.0.1:8000 --noreload >/tmp/cixis-smoke-back.log 2>&1 ) & BACK_PID=$!

until curl -s -o /dev/null http://127.0.0.1:8000/api/; do sleep 0.4; done
until curl -s -o /dev/null http://127.0.0.1:9000/menu/cixis-cafe/; do sleep 0.4; done
echo "   backend + remote up"

echo "== running flow =="
"$BACK_PY" - <<'PY'
import sys, requests
B = "http://127.0.0.1:8000/api"
R = "http://127.0.0.1:9000"
ok = True
def check(name, cond):
    global ok
    print(("  PASS " if cond else "  FAIL ") + name)
    ok = ok and cond

# revenue locked by default -> unlock endpoint
r = requests.post(f"{B}/revenue/unlock/", json={"password":"1234"}); check("revenue unlock (correct pw)", r.status_code==200 and "token" in r.json())
r = requests.post(f"{B}/revenue/unlock/", json={"password":"x"}); check("revenue unlock rejects wrong pw (401)", r.status_code==401)

# table -> order -> items -> payment
t = requests.post(f"{B}/tables/", json={"name":"میز ۱"}).json(); tid=t["id"]
o = requests.post(f"{B}/orders/", json={"mode":"table","table_id":tid}).json(); oid=o["id"]
prods = requests.get(f"{B}/products/").json(); p = prods[0]
requests.post(f"{B}/orders/{oid}/items/", json={"product_id":p["id"],"quantity":2})
od = requests.get(f"{B}/orders/{oid}/").json()
check("order subtotal = price*2", od["subtotal"]==p["price"]*2)
check("price snapshot stored", od["items"][0]["unit_price_snapshot"]==p["price"])

# partial then full payment
half = od["subtotal"]//2
requests.post(f"{B}/orders/{oid}/payments/", json={"amount":half,"method":"cash"})
od = requests.get(f"{B}/orders/{oid}/").json(); check("partial -> partially_paid", od["status"]=="partially_paid")
requests.post(f"{B}/orders/{oid}/payments/", json={"amount":od["remaining_amount"],"method":"card"})
od = requests.get(f"{B}/orders/{oid}/").json(); check("full -> paid, remaining 0", od["status"]=="paid" and od["remaining_amount"]==0)

# event order (no table)
ev = requests.post(f"{B}/orders/", json={"mode":"event","event_customer_label":"علی"})
check("event order without table (201)", ev.status_code==201 and ev.json()["event_customer_label"]=="علی")

# publish menu to remote, then read public QR menu
pub = requests.post(f"{B}/menu/publish/", json={}); check("menu publish success", pub.status_code==200 and pub.json().get("success") is True)
qr = requests.get(f"{R}/api/public/menu/cixis-cafe/"); check("QR menu JSON served", qr.status_code==200 and len(qr.json().get("categories",[]))==12)
html = requests.get(f"{R}/menu/cixis-cafe/"); check("QR menu HTML (RTL) served", html.status_code==200 and 'dir="rtl"' in html.text)

# day closing: settle remaining open (event) order is open -> confirm close
prev = requests.get(f"{B}/day-closing/preview/").json(); check("preview has totals", "total_sales" in prev)
close = requests.post(f"{B}/day-closing/close/", json={"confirm":True})
cj = close.json()
check("day close created (201) + backup", close.status_code==201 and cj.get("backup_path"))
# Sync is async (close returns immediately, per spec). Settle, then confirm no
# pending/failed sync records remain via the retry endpoint.
import time
synced = cj.get("sync_status") == "synced"
for _ in range(8):
    if synced:
        break
    rr = requests.post(f"{B}/sync/retry/").json()
    if rr.get("failed", 0) == 0 and (rr.get("synced", 0) >= 1 or rr.get("total", 0) == 0):
        synced = True
        break
    time.sleep(0.5)
check("day close synced to remote (async)", synced)

sys.exit(0 if ok else 1)
PY
RESULT=$?

echo
if [ "$RESULT" -eq 0 ]; then echo "==> SMOKE TEST PASSED"; else echo "==> SMOKE TEST FAILED (see /tmp/cixis-smoke-*.log)"; fi
exit $RESULT
