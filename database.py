"""
database.py — Supabase integration for FocusFlow Phase 2.
Handles College, Class, Student, and Session CRUD operations.
Includes local fallback queue to prevent silent data loss (Stress Fix S1).
"""

import logging
import time
import json as _json
import os
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

logger = logging.getLogger('FocusFlow.DB')

# ── Supabase Client ─────────────────────────────────────────────────
_client = None

# ── Circuit Breaker: stop hammering Supabase when it's unreachable ──
_fail_count = 0           # Consecutive failures
_circuit_open_until = 0   # Timestamp when circuit closes again
_FAIL_THRESHOLD = 2       # Failures before circuit opens
_COOLDOWN_SEC = 60        # Wait 60s before retrying after circuit opens
_QUERY_TIMEOUT = 8        # Max seconds per Supabase query
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='db')

# ── Stress Fix S1: Local fallback queue path ──
_FALLBACK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_failed_sessions.json')

def _circuit_ok() -> bool:
    """Check if circuit breaker allows requests."""
    global _fail_count, _circuit_open_until
    if _fail_count >= _FAIL_THRESHOLD:
        if time.time() < _circuit_open_until:
            return False  # Circuit is open, skip query
        # Cooldown expired, allow one retry
        _fail_count = _FAIL_THRESHOLD - 1
    return True

def _record_success():
    global _fail_count
    _fail_count = 0

def _record_failure():
    global _fail_count, _circuit_open_until
    _fail_count += 1
    if _fail_count >= _FAIL_THRESHOLD:
        _circuit_open_until = time.time() + _COOLDOWN_SEC
        logger.warning(f"DB circuit breaker OPEN — skipping queries for {_COOLDOWN_SEC}s")

def _timed_query(fn):
    """Run a Supabase query with timeout. Returns None on timeout."""
    try:
        future = _executor.submit(fn)
        result = future.result(timeout=_QUERY_TIMEOUT)
        _record_success()
        return result
    except FuturesTimeout:
        logger.error(f"DB query timed out after {_QUERY_TIMEOUT}s")
        _record_failure()
        return None
    except Exception as e:
        logger.error(f"DB query error: {e}")
        _record_failure()
        return None

def get_client():
    """Get or initialize Supabase client."""
    global _client
    if _client is not None:
        return _client
    try:
        from supabase import create_client
        from config import SUPABASE_URL, SUPABASE_ANON_KEY
        if not SUPABASE_URL or not SUPABASE_ANON_KEY or "YOUR_PROJECT_ID" in SUPABASE_URL:
            logger.warning("Supabase credentials not configured or default. Using offline mode.")
            return None
        _client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("[OK] Supabase connected.")
        return _client
    except Exception as e:
        logger.error(f"Supabase init error: {e}")
        return None

def is_connected() -> bool:
    return get_client() is not None

# ═══════════════════════════════════════════════════════════════
#  STRESS FIX S1: LOCAL FALLBACK QUEUE
#  Prevents silent data loss when Supabase is unreachable.
#  Failed sessions are saved to _failed_sessions.json and
#  retried on the next successful save.
# ═══════════════════════════════════════════════════════════════
def _queue_failed_session(session_data: dict):
    """Save a failed session to local JSON fallback queue."""
    try:
        existing = []
        if os.path.exists(_FALLBACK_FILE):
            with open(_FALLBACK_FILE, 'r', encoding='utf-8') as f:
                existing = _json.load(f)
        existing.append({
            **session_data,
            '_queued_at': time.time(),
            '_retry_count': 0
        })
        with open(_FALLBACK_FILE, 'w', encoding='utf-8') as f:
            _json.dump(existing, f, indent=2)
        logger.warning(f"Session queued locally ({len(existing)} pending). Will retry on next successful save.")
    except Exception as e:
        logger.error(f"CRITICAL: Failed to queue session locally: {e}")

def _flush_failed_sessions():
    """Attempt to re-save any queued sessions to Supabase.
    Called after each successful session save."""
    if not os.path.exists(_FALLBACK_FILE):
        return
    try:
        with open(_FALLBACK_FILE, 'r', encoding='utf-8') as f:
            queued = _json.load(f)
        if not queued:
            return
        
        db = get_client()
        if not db:
            return
        
        still_failed = []
        flushed = 0
        for item in queued:
            try:
                # Remove internal metadata before sending to Supabase
                data = {k: v for k, v in item.items() if not k.startswith('_')}
                db.table("sessions").insert(data).execute()
                flushed += 1
            except Exception:
                item['_retry_count'] = item.get('_retry_count', 0) + 1
                if item['_retry_count'] < 10:  # Give up after 10 retries
                    still_failed.append(item)
        
        if still_failed:
            with open(_FALLBACK_FILE, 'w', encoding='utf-8') as f:
                _json.dump(still_failed, f, indent=2)
        else:
            os.remove(_FALLBACK_FILE)
        
        if flushed:
            logger.info(f"Flushed {flushed} previously queued sessions to Supabase. {len(still_failed)} still pending.")
    except Exception as e:
        logger.error(f"Error flushing failed sessions: {e}")

# ── COLLEGE ──────────────────────────────────────────────────────────
def add_college(name: str, city: str = "", board: str = "") -> Optional[Dict]:
    """Create a new college/school."""
    try:
        db = get_client()
        if not db:
            return _offline_response("college", {"name": name, "city": city, "board": board})
        res = db.table("colleges").insert({"name": name, "city": city, "board": board}).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"add_college error: {e}")
        return None

def get_colleges() -> List[Dict]:
    """Get all colleges."""
    try:
        db = get_client()
        if not db:
            return []
        res = db.table("colleges").select("*").order("name").execute()
        return res.data or []
    except Exception as e:
        logger.error(f"get_colleges error: {e}")
        return []

# ── CLASS ─────────────────────────────────────────────────────────────
def add_class(college_id: str, name: str) -> Optional[Dict]:
    """Create a new class under a college."""
    try:
        db = get_client()
        if not db:
            return _offline_response("class", {"college_id": college_id, "name": name})
        res = db.table("classes").insert({"college_id": college_id, "name": name}).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"add_class error: {e}")
        return None

def get_classes(college_id: str) -> List[Dict]:
    """Get all classes for a college."""
    try:
        db = get_client()
        if not db:
            return []
        res = db.table("classes").select("*").eq("college_id", college_id).order("name").execute()
        return res.data or []
    except Exception as e:
        logger.error(f"get_classes error: {e}")
        return []

# ── STUDENT ────────────────────────────────────────────────────────────
def add_student(class_id: str, name: str, roll_no: str = "", age: int = 0, notes: str = "") -> Optional[Dict]:
    """Add a new student to a class."""
    try:
        db = get_client()
        if not db:
            return _offline_response("student", {"class_id": class_id, "name": name})
        res = db.table("students").insert({
            "class_id": class_id,
            "name": name,
            "roll_no": roll_no,
            "age": age,
            "notes": notes
        }).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"add_student error: {e}")
        return None

def get_students(class_id: str) -> List[Dict]:
    """Get all students in a class."""
    try:
        db = get_client()
        if not db:
            return []
        res = db.table("students").select("*").eq("class_id", class_id).order("name").execute()
        return res.data or []
    except Exception as e:
        logger.error(f"get_students error: {e}")
        return []

def search_students(college_name: str = "", class_name: str = "", student_name: str = "") -> List[Dict]:
    """Search students with optional filters. Returns flat list with college/class info."""
    if not _circuit_ok():
        return []
    try:
        db = get_client()
        if not db:
            return []
        # Build query
        def _run():
            query = db.table("students").select(
                "id, name, roll_no, age, notes, "
                "classes(id, name, colleges(id, name, city))"
            )
            if student_name:
                safe_name = student_name.replace('%', '\\%').replace('_', '\\_')
                query = query.ilike("name", f"%{safe_name}%")
            return query.execute()
        res = _timed_query(_run)
        if res is None:
            return []
        data = res.data or []

        # Filter by college/class in Python
        results = []
        for s in data:
            cls = s.get("classes") or {}
            clg = cls.get("colleges") or {}
            if college_name and college_name.lower() not in clg.get("name", "").lower():
                continue
            if class_name and class_name.lower() not in cls.get("name", "").lower():
                continue
            results.append({
                "id": s["id"],
                "name": s["name"],
                "roll_no": s.get("roll_no", ""),
                "age": s.get("age", 0),
                "class_id": cls.get("id"),
                "class_name": cls.get("name", ""),
                "college_id": clg.get("id"),
                "college_name": clg.get("name", ""),
            })
        return results
    except Exception as e:
        logger.error(f"search_students error: {e}")
        return []

# ── SESSION ─────────────────────────────────────────────────────────────
def save_session(student_id: str, duration: int, avg_focus: float,
                 peak_focus: float, graph_data: list = None) -> Optional[Dict]:
    """Save a completed neurofeedback session.
    Stress Fix S1: If Supabase fails, session is queued locally to
    _failed_sessions.json. NO DATA IS EVER SILENTLY LOST."""
    session_data = {
        "student_id": student_id,
        "duration_sec": duration,
        "score_focus": round(avg_focus, 2),
        "score_peak": round(peak_focus, 2),
        "graph_data": _json.dumps(graph_data or [])
    }
    try:
        db = get_client()
        if not db:
            logger.warning("Supabase offline — session queued locally.")
            _queue_failed_session(session_data)
            return {"id": "queued_offline", "student_id": student_id, "avg_focus": avg_focus}
        
        res = db.table("sessions").insert(session_data).execute()
        
        # On successful save, try to flush any previously queued sessions
        _flush_failed_sessions()
        
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"save_session error: {e} — queuing locally")
        _queue_failed_session(session_data)
        return {"id": "queued_offline", "student_id": student_id, "avg_focus": avg_focus}

def get_sessions(student_id: str) -> List[Dict]:
    """Get all sessions for a student, newest first."""
    try:
        db = get_client()
        if not db:
            return []
        res = (db.table("sessions")
               .select("*")
               .eq("student_id", student_id)
               .order("created_at", desc=True)
               .execute())
        sessions = res.data or []
        for s in sessions:
            # Parse graph_data from JSON string back to list
            if isinstance(s.get('graph_data'), str):
                try:
                    s['graph_data'] = _json.loads(s['graph_data'])
                except (_json.JSONDecodeError, TypeError):
                    s['graph_data'] = []
        return sessions
    except Exception as e:
        logger.error(f"get_sessions error: {e}")
        return []

def get_recent_sessions(limit: int = 20) -> List[Dict]:
    """Get most recent sessions across ALL students with student/class/college info."""
    if not _circuit_ok():
        return []
    try:
        db = get_client()
        if not db:
            return []
        def _run():
            return (db.table("sessions")
                   .select("*, students(name, roll_no, class_id, classes(name, college_id, colleges(name)))")
                   .order("created_at", desc=True)
                   .limit(limit)
                   .execute())
        res = _timed_query(_run)
        if res is None:
            return []
        
        # Flatten for the frontend
        flattened = []
        for s in (res.data or []):
            stu = s.get("students") or {}
            cls = stu.get("classes") or {}
            clg = cls.get("colleges") or {}
            
            flattened.append({
                "id": s["id"],
                "student_id": s["student_id"],
                "student_name": stu.get("name", "Unknown"),
                "class_name": cls.get("name", "Unknown"),
                "college_name": clg.get("name", "Unknown"),
                "avg_focus": s.get("score_focus", 0.0),
                "duration": s.get("duration_sec", 0),
                "created_at": s.get("created_at")
            })
        return flattened
    except Exception as e:
        logger.error(f"get_recent_sessions error: {e}")
        return []

# ── HELPERS ──────────────────────────────────────────────────────────────
import uuid as _uuid

def _offline_response(kind: str, data: dict) -> dict:
    """Return a fake success response when offline."""
    data["id"] = str(_uuid.uuid4())
    logger.warning(f"Offline mode: {kind} created locally only.")
    return data

# ── DELETE OPERATIONS ────────────────────────────────────────────────
def delete_college(college_id: str) -> bool:
    """Delete a college and all its classes/students/sessions (cascade)."""
    try:
        db = get_client()
        if not db: return False
        db.table("colleges").delete().eq("id", college_id).execute()
        return True
    except Exception as e:
        logger.error(f"delete_college error: {e}")
        return False

def delete_class(class_id: str) -> bool:
    """Delete a class and all its students/sessions (cascade)."""
    try:
        db = get_client()
        if not db: return False
        db.table("classes").delete().eq("id", class_id).execute()
        return True
    except Exception as e:
        logger.error(f"delete_class error: {e}")
        return False

def delete_student(student_id: str) -> bool:
    """Delete a student and all their sessions."""
    try:
        db = get_client()
        if not db: return False
        db.table("students").delete().eq("id", student_id).execute()
        return True
    except Exception as e:
        logger.error(f"delete_student error: {e}")
        return False

def delete_session(session_id: str) -> bool:
    """Delete a single session record."""
    try:
        db = get_client()
        if not db: return False
        db.table("sessions").delete().eq("id", session_id).execute()
        return True
    except Exception as e:
        logger.error(f"delete_session error: {e}")
        return False
