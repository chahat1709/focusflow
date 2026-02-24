"""Full end-to-end test of all FocusFlow API endpoints."""
import requests, sys

BASE = 'http://127.0.0.1:5077'
passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name} {detail}")
    else:
        failed += 1
        print(f"  FAIL  {name} {detail}")

print("=" * 60)
print("  FocusFlow — Full End-to-End Test Suite")
print("=" * 60)

# 1. Dashboard loads
print("\n[1] Dashboard HTML")
r = requests.get(f'{BASE}/')
test("Page loads", r.status_code == 200, f"status={r.status_code}")
test("Has session-controls div", "session-controls" in r.text)
test("REC button REMOVED", 'onclick="startSession()"' not in r.text)
test("STOP button exists (hidden)", "stopSessionBtn" in r.text)

# 2. Status endpoint
print("\n[2] /api/status")
r = requests.get(f'{BASE}/api/status')
d = r.json()
test("Status returns 200", r.status_code == 200)
test("Has 'connected' field", "connected" in d)
test("Has 'baseline_done' field", "baseline_done" in d)

# 3. DB status
print("\n[3] /api/db/status")
r = requests.get(f'{BASE}/api/db/status')
d = r.json()
test("DB status returns 200", r.status_code == 200)
test("Supabase connected", d.get("connected") == True, f"connected={d.get('connected')}")

# 4. Colleges
print("\n[4] /api/colleges")
r = requests.get(f'{BASE}/api/colleges')
test("Colleges returns 200", r.status_code == 200)
test("Returns a list", isinstance(r.json(), list), f"count={len(r.json())}")

# 5. Recent sessions
print("\n[5] /api/db/recent")
r = requests.get(f'{BASE}/api/db/recent')
test("Recent sessions returns 200", r.status_code == 200)
test("Returns a list", isinstance(r.json(), list), f"count={len(r.json())}")

# 6. Student search
print("\n[6] /api/students/search")
r = requests.get(f'{BASE}/api/students/search')
test("Search returns 200", r.status_code == 200)
test("Returns a list", isinstance(r.json(), list), f"count={len(r.json())}")

# 7. Session start (baseline reset)
print("\n[7] /api/session/start (POST)")
r = requests.post(f'{BASE}/api/session/start')
d = r.json()
test("Session start returns 200", r.status_code == 200)
test("Returns ok status", d.get("status") == "ok", f"response={d}")

# 8. Report generation
print("\n[8] /api/report/<id>")
r = requests.get(f'{BASE}/api/report/test-id?name=TestStudent&roll_no=101&age=15&class_name=ClassA&college_name=CollegeB')
test("Report returns 200", r.status_code == 200)
test("Returns PDF content-type", "application/pdf" in r.headers.get("content-type", ""))
test("PDF has content", len(r.content) > 500, f"size={len(r.content)} bytes")

# 9. JS file checks
print("\n[9] dashboard_therapeutic.js")
r = requests.get(f'{BASE}/dashboard_therapeutic.js')
test("JS file loads", r.status_code == 200)
test("Has connection check guard", "Connect the Muse headband first" in r.text)
test("Has stopSessionBtn reference", "stopSessionBtn" in r.text)
test("Has 5-min timer constant", "SESSION_DURATION_SEC = 300" in r.text)
test("Has _startSessionInternal", "_startSessionInternal" in r.text)
test("Has encodeURIComponent in downloadReport", "encodeURIComponent" in r.text)
test("No recursive startSession bug", "window.startSession = startSession" in r.text)

# 10. Calibrate endpoint
print("\n[10] /api/calibrate")
r = requests.post(f'{BASE}/api/calibrate')
test("Calibrate returns 200", r.status_code == 200)

print("\n" + "=" * 60)
print(f"  RESULTS: {passed} passed, {failed} failed, {passed+failed} total")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
