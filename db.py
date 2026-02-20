import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def norm(v: Any) -> str:
    return (v or "").strip() if isinstance(v, str) else ("" if v is None else str(v).strip())
def safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        s = str(x).strip()
        if not s:
            return default
        return int(float(s))
    except Exception:
        return default
class DB:
    """
    SQLite data access layer.
    Performance improvements applied:
    - WAL + NORMAL synchronous + MEMORY temp store + tuned cache size.
    - bulk writes with executemany.
    - single-row upserts for common edit flows (avoid full-table rewrite).
    - SQL-side filtering for roster listing.
    """
    ROSTER_COLS = [
        "id", "emp_no", "name", "english_name", "nationality", "gender", "employment_status",
        "hire_date", "leave_date", "referrer", "workplace", "dorm", "passport_no", "bank",
        "account_no", "health_expiry", "health_file_path", "bankbook_path", "passport_path",
        "contract_path", "special_note", "is_trashed", "trashed_at", "created_at", "updated_at",
    ]
    AGENCY_COLS = [
        "id", "emp_id", "emp_no", "name", "referrer", "payee", "fee", "paid", "paid_date",
        "note", "created_at", "updated_at", "is_trashed",
    ]
    def __init__(self, db_file: str, data_dir: str):
        self.db_file = db_file
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.conn = sqlite3.connect(self.db_file, timeout=8.0)
        self.conn.row_factory = sqlite3.Row
        self._apply_pragmas()
    def _apply_pragmas(self):
        # DB responsiveness & concurrency tuning
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA temp_store=MEMORY;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        # negative => KiB units. -32768 ~= 32MB page cache.
        self.conn.execute("PRAGMA cache_size=-32768;")
    def close(self):
        try:
            if getattr(self, "conn", None) is not None:
                self.conn.close()
        except Exception:
            pass
    def init_db(self):
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS roster (
                  id TEXT PRIMARY KEY,
                  emp_no TEXT,
                  name TEXT,
                  english_name TEXT,
                  nationality TEXT,
                  gender TEXT,
                  employment_status TEXT,
                  hire_date TEXT,
                  leave_date TEXT,
                  referrer TEXT,
                  workplace TEXT,
                  dorm TEXT,
                  passport_no TEXT,
                  bank TEXT,
                  account_no TEXT,
                  health_expiry TEXT,
                  health_file_path TEXT,
                  bankbook_path TEXT,
                  passport_path TEXT,
                  contract_path TEXT,
                  special_note TEXT,
                  is_trashed INTEGER DEFAULT 0,
                  trashed_at TEXT DEFAULT '',
                  created_at TEXT,
                  updated_at TEXT
                )
                """
            )
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_roster_empno ON roster(emp_no)",
                "CREATE INDEX IF NOT EXISTS idx_roster_name ON roster(name)",
                "CREATE INDEX IF NOT EXISTS idx_roster_status ON roster(employment_status)",
                "CREATE INDEX IF NOT EXISTS idx_roster_workplace ON roster(workplace)",
                "CREATE INDEX IF NOT EXISTS idx_roster_trashed ON roster(is_trashed)",
                "CREATE INDEX IF NOT EXISTS idx_roster_dorm ON roster(dorm)",
                "CREATE INDEX IF NOT EXISTS idx_roster_updated ON roster(updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_roster_trash_status_work ON roster(is_trashed, employment_status, workplace)",
                "CREATE INDEX IF NOT EXISTS idx_roster_trash_status_dorm ON roster(is_trashed, employment_status, dorm)",
            ]:
                self.conn.execute(idx_sql)
            # Deduplicate by emp_no before enabling UNIQUE index.
            self._dedupe_roster_emp_no()
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_roster_empno_unique ON roster(emp_no) WHERE emp_no IS NOT NULL AND emp_no <> ''")
            self.conn.execute("CREATE TABLE IF NOT EXISTS standards_workplaces (name TEXT PRIMARY KEY, need INTEGER DEFAULT 0)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS standards_dorms (name TEXT PRIMARY KEY, capacity INTEGER DEFAULT 0, fee INTEGER DEFAULT 0)")
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS org_chart (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  team TEXT,
                  role TEXT,
                  name TEXT,
                  note TEXT,
                  updated_at TEXT
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agency_fees (
                  id TEXT PRIMARY KEY,
                  emp_id TEXT,
                  emp_no TEXT,
                  name TEXT,
                  referrer TEXT,
                  payee TEXT,
                  fee INTEGER,
                  paid TEXT,
                  paid_date TEXT,
                  note TEXT,
                  created_at TEXT,
                  updated_at TEXT,
                  is_trashed INTEGER DEFAULT 0
                )
                """
            )
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_fee_paid ON agency_fees(paid)",
                "CREATE INDEX IF NOT EXISTS idx_fee_payee ON agency_fees(payee)",
                "CREATE INDEX IF NOT EXISTS idx_fee_emp ON agency_fees(emp_id)",
                "CREATE INDEX IF NOT EXISTS idx_fee_updated ON agency_fees(updated_at)",
            ]:
                self.conn.execute(idx_sql)
            self.conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    def _dedupe_roster_emp_no(self):
        dupes = self.conn.execute(
            "SELECT emp_no FROM roster WHERE emp_no IS NOT NULL AND emp_no<>'' GROUP BY emp_no HAVING COUNT(*) > 1"
        ).fetchall()
        for row in dupes:
            emp_no = row[0]
            rows = self.conn.execute(
                "SELECT id, updated_at FROM roster WHERE emp_no=? ORDER BY COALESCE(updated_at,'') DESC, id DESC",
                (emp_no,),
            ).fetchall()
            keep_id = rows[0][0] if rows else ""
            for r in rows[1:]:
                self.conn.execute("UPDATE roster SET emp_no='' WHERE id=?", (r[0],))
            if keep_id:
                self.conn.execute("UPDATE roster SET emp_no=? WHERE id=?", (emp_no, keep_id))
    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default
    def set_setting(self, key: str, value: Any):
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )
    def _read_json(self, path: str, default: Any):
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    def _roster_payload(self, r: Dict[str, Any]) -> Dict[str, Any]:
        rid = norm(r.get("id")) or uuid.uuid4().hex
        return {
            "id": rid,
            "emp_no": norm(r.get("emp_no")),
            "name": norm(r.get("name")),
            "english_name": norm(r.get("english_name")),
            "nationality": norm(r.get("nationality")),
            "gender": norm(r.get("gender")),
            "employment_status": norm(r.get("employment_status")) or "재직",
            "hire_date": norm(r.get("hire_date")),
            "leave_date": norm(r.get("leave_date")),
            "referrer": norm(r.get("referrer")),
            "workplace": norm(r.get("workplace")),
            "dorm": norm(r.get("dorm")),
            "passport_no": norm(r.get("passport_no")),
            "bank": norm(r.get("bank")),
            "account_no": norm(r.get("account_no")),
            "health_expiry": norm(r.get("health_expiry")),
            "health_file_path": norm(r.get("health_file_path")),
            "bankbook_path": norm(r.get("bankbook_path")),
            "passport_path": norm(r.get("passport_path")),
            "contract_path": norm(r.get("contract_path")),
            "special_note": norm(r.get("special_note")),
            "is_trashed": safe_int(r.get("is_trashed", 0), 0),
            "trashed_at": norm(r.get("trashed_at")),
            "created_at": norm(r.get("created_at")) or now_str(),
            "updated_at": norm(r.get("updated_at")) or now_str(),
        }
    def _agency_payload(self, r: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": norm(r.get("id")) or uuid.uuid4().hex,
            "emp_id": norm(r.get("emp_id")),
            "emp_no": norm(r.get("emp_no")),
            "name": norm(r.get("name")),
            "referrer": norm(r.get("referrer")),
            "payee": norm(r.get("payee")),
            "fee": safe_int(r.get("fee", 0), 0),
            "paid": norm(r.get("paid")) or "미지급",
            "paid_date": norm(r.get("paid_date")),
            "note": norm(r.get("note")),
            "created_at": norm(r.get("created_at")) or now_str(),
            "updated_at": norm(r.get("updated_at")) or now_str(),
            "is_trashed": safe_int(r.get("is_trashed", 0), 0),
        }
    def _rows_for_executemany(self, cols: List[str], payloads: Iterable[Dict[str, Any]]) -> List[Tuple[Any, ...]]:
        return [tuple(p[c] for c in cols) for p in payloads]
    def migrate_from_json_if_needed(self):
        # keep one-time behavior
        if self.get_setting("db_migrated", "0") == "1":
            return
        roster_json = self._read_json(os.path.join(self.data_dir, "roster.json"), [])
        agency_json = self._read_json(os.path.join(self.data_dir, "agency_fees.json"), [])
        standards_json = self._read_json(os.path.join(self.data_dir, "standards.json"), {})
        org_json = self._read_json(os.path.join(self.data_dir, "org_chart.json"), [])
        settings_json = self._read_json(os.path.join(self.data_dir, "settings.json"), {})
        with self.conn:
            roster_payloads = [self._roster_payload(r) for r in (roster_json if isinstance(roster_json, list) else []) if isinstance(r, dict)]
            if roster_payloads:
                self.conn.executemany(
                    f"INSERT INTO roster ({','.join(self.ROSTER_COLS)}) VALUES ({','.join(['?']*len(self.ROSTER_COLS))}) "
                    f"ON CONFLICT(id) DO UPDATE SET "
                    + ",".join([f"{c}=excluded.{c}" for c in self.ROSTER_COLS if c != "id"]),
                    self._rows_for_executemany(self.ROSTER_COLS, roster_payloads),
                )
            agency_payloads = [self._agency_payload(r) for r in (agency_json if isinstance(agency_json, list) else []) if isinstance(r, dict)]
            if agency_payloads:
                self.conn.executemany(
                    f"INSERT INTO agency_fees ({','.join(self.AGENCY_COLS)}) VALUES ({','.join(['?']*len(self.AGENCY_COLS))}) "
                    f"ON CONFLICT(id) DO UPDATE SET "
                    + ",".join([f"{c}=excluded.{c}" for c in self.AGENCY_COLS if c != "id"]),
                    self._rows_for_executemany(self.AGENCY_COLS, agency_payloads),
                )
            self.conn.execute("DELETE FROM standards_workplaces")
            wp_rows = []
            for w in (standards_json.get("workplaces") if isinstance(standards_json, dict) else []) or []:
                if isinstance(w, str):
                    name, need = norm(w), 0
                else:
                    name, need = norm(w.get("name")), safe_int(w.get("need", 0), 0)
                if name:
                    wp_rows.append((name, need))
            if wp_rows:
                self.conn.executemany("INSERT INTO standards_workplaces(name,need) VALUES(?,?)", wp_rows)
            self.conn.execute("DELETE FROM standards_dorms")
            dorm_rows = []
            for d in (standards_json.get("dorms") if isinstance(standards_json, dict) else []) or []:
                if isinstance(d, str):
                    name, cap, fee = norm(d), 0, 0
                else:
                    name, cap, fee = norm(d.get("name")), safe_int(d.get("capacity", 0), 0), safe_int(d.get("fee", 0), 0)
                if name:
                    dorm_rows.append((name, cap, fee))
            if dorm_rows:
                self.conn.executemany("INSERT INTO standards_dorms(name,capacity,fee) VALUES(?,?,?)", dorm_rows)
            self.conn.execute("DELETE FROM org_chart")
            org_rows = []
            for r in org_json if isinstance(org_json, list) else []:
                if isinstance(r, dict):
                    org_rows.append((norm(r.get("team")), norm(r.get("role")), norm(r.get("name")), norm(r.get("note")), now_str()))
            if org_rows:
                self.conn.executemany("INSERT INTO org_chart(team,role,name,note,updated_at) VALUES(?,?,?,?,?)", org_rows)
            if isinstance(settings_json, dict):
                self.conn.executemany(
                    "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    [(str(k), str(v)) for k, v in settings_json.items()],
                )
        backup_dir = os.path.join(self.data_dir, "legacy_json_backup")
        os.makedirs(backup_dir, exist_ok=True)
        for fname in ["roster.json", "agency_fees.json", "standards.json", "org_chart.json", "settings.json"]:
            src = os.path.join(self.data_dir, fname)
            if os.path.exists(src):
                dst = os.path.join(backup_dir, fname)
                if not os.path.exists(dst):
                    shutil.move(src, dst)
        self.set_setting("db_migrated", "1")
    def list_roster(
        self,
        include_trashed: bool = True,
        search_text: str = "",
        workplace: str = "",
        status: str = "",
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        where = []
        params: List[Any] = []
        if not include_trashed:
            where.append("is_trashed=0")
        if workplace and workplace != "전체":
            where.append("workplace=?")
            params.append(workplace)
        if status and status != "전체":
            where.append("employment_status=?")
            params.append(status)
        if search_text:
            like = f"%{search_text}%"
            where.append("(name LIKE ? OR english_name LIKE ? OR emp_no LIKE ?)")
            params.extend([like, like, like])
        sql = "SELECT * FROM roster"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC, id DESC"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([int(limit), int(max(offset, 0))])
        rows = self.conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]
    def upsert_roster(self, item: Dict[str, Any]):
        payload = self._roster_payload(item)
        with self.conn:
            self.conn.execute(
                f"INSERT INTO roster ({','.join(self.ROSTER_COLS)}) VALUES ({','.join(['?']*len(self.ROSTER_COLS))}) "
                f"ON CONFLICT(id) DO UPDATE SET "
                + ",".join([f"{c}=excluded.{c}" for c in self.ROSTER_COLS if c != "id"]),
                tuple(payload[c] for c in self.ROSTER_COLS),
            )
    def upsert_roster_many(self, items: List[Dict[str, Any]]):
        payloads = [self._roster_payload(r) for r in (items or [])]
        if not payloads:
            return
        with self.conn:
            self.conn.executemany(
                f"INSERT INTO roster ({','.join(self.ROSTER_COLS)}) VALUES ({','.join(['?']*len(self.ROSTER_COLS))}) "
                f"ON CONFLICT(id) DO UPDATE SET "
                + ",".join([f"{c}=excluded.{c}" for c in self.ROSTER_COLS if c != "id"]),
                self._rows_for_executemany(self.ROSTER_COLS, payloads),
            )
    def replace_all_roster(self, items: Iterable[Dict[str, Any]]):
        payloads = [self._roster_payload(r) for r in (items or [])]
        with self.conn:
            self.conn.execute("DELETE FROM roster")
            if payloads:
                self.conn.executemany(
                    f"INSERT INTO roster ({','.join(self.ROSTER_COLS)}) VALUES ({','.join(['?']*len(self.ROSTER_COLS))})",
                    self._rows_for_executemany(self.ROSTER_COLS, payloads),
                )
    def trash_roster(self, rid: str):
        with self.conn:
            self.conn.execute("UPDATE roster SET is_trashed=1, trashed_at=?, updated_at=? WHERE id=?", (now_str(), now_str(), rid))
    def restore_roster(self, rid: str):
        with self.conn:
            self.conn.execute("UPDATE roster SET is_trashed=0, trashed_at='', updated_at=? WHERE id=?", (now_str(), rid))
    def hard_delete_roster(self, rid: str):
        with self.conn:
            self.conn.execute("DELETE FROM roster WHERE id=?", (rid,))
    def list_agency_fees(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM agency_fees ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]
    def upsert_agency_fee(self, item: Dict[str, Any]):
        payload = self._agency_payload(item)
        with self.conn:
            self.conn.execute(
                f"INSERT INTO agency_fees ({','.join(self.AGENCY_COLS)}) VALUES ({','.join(['?']*len(self.AGENCY_COLS))}) "
                f"ON CONFLICT(id) DO UPDATE SET "
                + ",".join([f"{c}=excluded.{c}" for c in self.AGENCY_COLS if c != "id"]),
                tuple(payload[c] for c in self.AGENCY_COLS),
            )
    def upsert_agency_fee_many(self, items: List[Dict[str, Any]]):
        payloads = [self._agency_payload(r) for r in (items or [])]
        if not payloads:
            return
        with self.conn:
            self.conn.executemany(
                f"INSERT INTO agency_fees ({','.join(self.AGENCY_COLS)}) VALUES ({','.join(['?']*len(self.AGENCY_COLS))}) "
                f"ON CONFLICT(id) DO UPDATE SET "
                + ",".join([f"{c}=excluded.{c}" for c in self.AGENCY_COLS if c != "id"]),
                self._rows_for_executemany(self.AGENCY_COLS, payloads),
            )
    def replace_all_agency_fees(self, rows: Iterable[Dict[str, Any]]):
        payloads = [self._agency_payload(r) for r in (rows or [])]
        with self.conn:
            self.conn.execute("DELETE FROM agency_fees")
            if payloads:
                self.conn.executemany(
                    f"INSERT INTO agency_fees ({','.join(self.AGENCY_COLS)}) VALUES ({','.join(['?']*len(self.AGENCY_COLS))})",
                    self._rows_for_executemany(self.AGENCY_COLS, payloads),
                )
    def delete_agency_fee(self, fee_id: str):
        with self.conn:
            self.conn.execute("DELETE FROM agency_fees WHERE id=?", (fee_id,))
    def get_standards(self) -> Dict[str, Any]:
        wp = [dict(r) for r in self.conn.execute("SELECT name,need FROM standards_workplaces ORDER BY name").fetchall()]
        dm = [dict(r) for r in self.conn.execute("SELECT name,capacity,fee FROM standards_dorms ORDER BY name").fetchall()]
        return {"workplaces": wp, "dorms": dm, "updated_at": now_str()}
    def save_standards(self, workplaces: Iterable[Any], dorms: Iterable[Any]):
        wp_rows = []
        for w in workplaces or []:
            if isinstance(w, str):
                name, need = norm(w), 0
            else:
                name, need = norm(w.get("name")), safe_int(w.get("need", 0), 0)
            if name:
                wp_rows.append((name, need))
        dorm_rows = []
        for d in dorms or []:
            if isinstance(d, str):
                name, cap, fee = norm(d), 0, 0
            else:
                name, cap, fee = norm(d.get("name")), safe_int(d.get("capacity", 0), 0), safe_int(d.get("fee", 0), 0)
            if name:
                dorm_rows.append((name, cap, fee))
        with self.conn:
            self.conn.execute("DELETE FROM standards_workplaces")
            if wp_rows:
                self.conn.executemany("INSERT INTO standards_workplaces(name,need) VALUES(?,?)", wp_rows)
            self.conn.execute("DELETE FROM standards_dorms")
            if dorm_rows:
                self.conn.executemany("INSERT INTO standards_dorms(name,capacity,fee) VALUES(?,?,?)", dorm_rows)
    def list_org_chart(self) -> List[Dict[str, Any]]:
        return [dict(r) for r in self.conn.execute("SELECT team,role,name,note FROM org_chart ORDER BY id").fetchall()]
    def list_workplace_status_counts(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT workplace, employment_status, COUNT(*) AS cnt
            FROM roster
            WHERE is_trashed=0
            GROUP BY workplace, employment_status
            """
        ).fetchall()
        return [dict(r) for r in rows]
    def list_dorm_occupancy_counts(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT dorm, COUNT(*) AS cnt
            FROM roster
            WHERE is_trashed=0 AND employment_status='재직' AND dorm<>''
            GROUP BY dorm
            ORDER BY dorm
            """
        ).fetchall()
        return [dict(r) for r in rows]
    def list_dorm_occupants_names(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT d.dorm,
                   (
                     SELECT group_concat(name, ', ')
                     FROM (
                       SELECT name
                       FROM roster r2
                       WHERE r2.is_trashed=0
                         AND r2.employment_status='재직'
                         AND r2.dorm=d.dorm
                         AND r2.name<>''
                       ORDER BY r2.name
                     )
                   ) AS names
            FROM (
              SELECT DISTINCT dorm
              FROM roster
              WHERE is_trashed=0 AND employment_status='재직' AND dorm<>''
            ) d
            ORDER BY d.dorm
            """
        ).fetchall()
        return [dict(r) for r in rows]
    def save_org_chart(self, rows: Iterable[Dict[str, Any]]):
        payload = [
            (norm(r.get("team")), norm(r.get("role")), norm(r.get("name")), norm(r.get("note")), now_str())
            for r in (rows or [])
        ]
        with self.conn:
            self.conn.execute("DELETE FROM org_chart")
            if payload:
                self.conn.executemany(
                    "INSERT INTO org_chart(team,role,name,note,updated_at) VALUES(?,?,?,?,?)",
                    payload,
                )
