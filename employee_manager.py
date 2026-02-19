# -*- coding: utf-8 -*-
import os
import json
import uuid
import shutil
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from tksheet import Sheet  # pip install tksheet


# ============================
# Storage paths
# ============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

BANKBOOK_DIR = os.path.join(UPLOAD_DIR, "bankbook")
PASSPORT_DIR = os.path.join(UPLOAD_DIR, "passport")
CONTRACT_DIR = os.path.join(UPLOAD_DIR, "contract")
HEALTH_DIR = os.path.join(UPLOAD_DIR, "health")

DB_FILE = os.path.join(DATA_DIR, "roster.json")
STANDARDS_FILE = os.path.join(DATA_DIR, "standards.json")

for d in [DATA_DIR, UPLOAD_DIR, BANKBOOK_DIR, PASSPORT_DIR, CONTRACT_DIR, HEALTH_DIR]:
    os.makedirs(d, exist_ok=True)


# ============================
# Helpers
# ============================
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return date.today().strftime("%Y-%m-%d")


def norm(s: str) -> str:
    return (s or "").strip()


def safe_int(x, default=0):
    try:
        if x is None:
            return default
        s = str(x).strip()
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default


def safe_name(name: str) -> str:
    s = "".join(c for c in (name or "").strip() if c.isalnum() or c in " _-가-힣").strip()
    s = s.replace(" ", "_")
    return s if s else "unknown"


def copy_to_upload(src_path: str, dst_folder: str, person_name: str, kind: str) -> str:
    if not src_path:
        return ""
    ext = os.path.splitext(src_path)[1].lower() or ".bin"
    uid = uuid.uuid4().hex[:8]
    dst_name = f"{safe_name(person_name)}_{kind}_{uid}{ext}"
    dst_abs = os.path.join(dst_folder, dst_name)
    shutil.copy2(src_path, dst_abs)
    return os.path.relpath(dst_abs, BASE_DIR).replace("\\", "/")


def short_file(p: str) -> str:
    return os.path.basename(p) if p else ""


def parse_yyyy_mm_dd(s: str):
    s = norm(s)
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return "invalid"


def health_expiry_flag(expiry_str: str) -> str:
    dt = parse_yyyy_mm_dd(expiry_str)
    if dt is None:
        return "none"
    if dt == "invalid":
        return "invalid"
    today = date.today()
    if dt < today:
        return "expired"
    if (dt - today).days <= 30:
        return "soon"
    return "ok"


def abs_path(rel_or_abs: str) -> str:
    p = norm(rel_or_abs)
    if not p:
        return ""
    if os.path.isabs(p):
        return p
    return os.path.join(BASE_DIR, p)


def open_file_with_default_app(path_rel_or_abs: str):
    p = abs_path(path_rel_or_abs)
    if not p or not os.path.exists(p):
        messagebox.showwarning("확인", "파일이 존재하지 않습니다.")
        return
    try:
        os.startfile(p)  # Windows
    except Exception as e:
        messagebox.showwarning("확인", f"파일 열기 실패: {e}")


def generate_emp_no(items, hire_date_str: str) -> str:
    dt = parse_yyyy_mm_dd(hire_date_str)
    if dt in (None, "invalid"):
        return ""
    base = dt.strftime("%Y%m%d")
    used = set()
    for r in items:
        eno = norm(r.get("emp_no", ""))
        if eno.startswith(base + "-"):
            used.add(eno)
    seq = 1
    while True:
        cand = f"{base}-{seq:02d}"
        if cand not in used:
            return cand
        seq += 1


# ============================
# Standards (마스터 목록) 관리
# - workplaces: [{"name": "...", "need": 0}, ...] 또는 ["..."]
# - dorms: [{"name":"하랑빌101호","capacity":2,"fee":200000}, ...] 또는 ["..."]
# ============================
def default_standards():
    return {
        "workplaces": [
            {"name": "훈제인원", "need": 0},
            {"name": "도압인원", "need": 0},
        ],
        "dorms": [
            {"name": f"하랑빌{n}호", "capacity": 0, "fee": 0} for n in range(101, 206)
        ],
        "updated_at": now_str()
    }


def load_standards():
    """
    standards.json이 과거 버전처럼 문자열 리스트로 저장되어 있어도 자동 복구
    - workplaces: ["훈제인원", ...] -> [{"name":"훈제인원","need":0}, ...]
    - dorms: ["하랑빌101호", ...] -> [{"name":"하랑빌101호","capacity":0,"fee":0}, ...]
    """
    dft = default_standards()
    if not os.path.exists(STANDARDS_FILE):
        return dft

    try:
        with open(STANDARDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return dft

    workplaces = data.get("workplaces", dft["workplaces"])
    dorms = data.get("dorms", dft["dorms"])

    # ---- workplaces normalize (dict OR str 모두 지원)
    wp_seen = set()
    wp_out = []
    for w in (workplaces or []):
        if isinstance(w, str):
            name = norm(w)
            need = 0
        elif isinstance(w, dict):
            name = norm(w.get("name", ""))
            need = safe_int(w.get("need", 0), 0)
        else:
            continue

        if not name or name in wp_seen:
            continue
        wp_seen.add(name)
        wp_out.append({"name": name, "need": need})

    # ---- dorms normalize (dict OR str 모두 지원)
    dorm_seen = set()
    dorm_out = []
    for r in (dorms or []):
        if isinstance(r, str):
            name = norm(r)
            cap = 0
            fee = 0
        elif isinstance(r, dict):
            name = norm(r.get("name", ""))
            cap = safe_int(r.get("capacity", 0), 0)
            fee = safe_int(r.get("fee", 0), 0)
        else:
            continue

        if not name or name in dorm_seen:
            continue
        dorm_seen.add(name)
        dorm_out.append({"name": name, "capacity": cap, "fee": fee})

    return {
        "workplaces": wp_out if wp_out else dft["workplaces"],
        "dorms": dorm_out if dorm_out else dft["dorms"],
        "updated_at": data.get("updated_at", now_str())
    }


def save_standards(workplaces, dorms):
    # workplaces: [{"name":..., "need":...}] or ["..."] 모두 허용
    wp_seen = set()
    wp_out = []
    for w in (workplaces or []):
        if isinstance(w, str):
            name = norm(w)
            need = 0
        else:
            name = norm((w or {}).get("name", ""))
            need = safe_int((w or {}).get("need", 0), 0)

        if not name or name in wp_seen:
            continue
        wp_seen.add(name)
        wp_out.append({"name": name, "need": need})

    # dorms: [{"name":..., "capacity":..., "fee":...}] or ["..."] 모두 허용
    dorm_seen = set()
    dorm_out = []
    for r in (dorms or []):
        if isinstance(r, str):
            name = norm(r)
            cap = 0
            fee = 0
        else:
            name = norm((r or {}).get("name", ""))
            cap = safe_int((r or {}).get("capacity", 0), 0)
            fee = safe_int((r or {}).get("fee", 0), 0)

        if not name or name in dorm_seen:
            continue
        dorm_seen.add(name)
        dorm_out.append({"name": name, "capacity": cap, "fee": fee})

    data = {
        "workplaces": wp_out,
        "dorms": dorm_out,
        "updated_at": now_str()
    }
    with open(STANDARDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def standards_workplace_names(stds):
    return [""] + [w["name"] for w in (stds.get("workplaces") or []) if norm(w.get("name"))]


def standards_dorm_names(stds):
    return [""] + [r["name"] for r in (stds.get("dorms") or []) if norm(r.get("name"))]


def standards_need_map(stds):
    mp = {}
    for w in stds.get("workplaces") or []:
        mp[norm(w.get("name"))] = safe_int(w.get("need", 0), 0)
    return mp


def standards_dorm_map(stds):
    mp = {}
    for r in stds.get("dorms") or []:
        mp[norm(r.get("name"))] = {
            "capacity": safe_int(r.get("capacity", 0), 0),
            "fee": safe_int(r.get("fee", 0), 0)
        }
    return mp


# ============================
# DB
# ============================
def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            items = json.load(f)
        except json.JSONDecodeError:
            items = []

    for rec in items:
        rec.setdefault("id", uuid.uuid4().hex)
        rec.setdefault("emp_no", "")
        rec.setdefault("name", "")
        rec.setdefault("gender", "")
        rec.setdefault("employment_status", "재직")  # 재직/퇴사
        rec.setdefault("hire_date", "")
        rec.setdefault("leave_date", "")
        rec.setdefault("referrer", "")

        rec.setdefault("workplace", "")
        rec.setdefault("dorm", "")
        rec.setdefault("bank", "")
        rec.setdefault("account_no", "")

        rec.setdefault("health_expiry", "")
        rec.setdefault("health_file_path", "")
        rec.setdefault("bankbook_path", "")
        rec.setdefault("passport_path", "")
        rec.setdefault("contract_path", "")

        rec.setdefault("created_at", now_str())
        rec.setdefault("updated_at", rec.get("created_at", now_str()))
    return items


def save_db(items):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


# ============================
# GUI App
# ============================
class RosterApp(tk.Tk):
    BOX_OFF = "□"
    BOX_ON = "■"

    def __init__(self):
        super().__init__()
        self.title("인력명부 프로그램")
        self.geometry("1650x900")
        self.minsize(1400, 760)

        self.items = load_db()
        self.selected_id = None

        # 체크(하나만): 클릭=체크 토글 + 즉시 불러오기
        self.checked_ids = set()
        self.row_id_map = []

        self.standards = load_standards()
        self.workplace_names = standards_workplace_names(self.standards)
        self.dorm_names = standards_dorm_names(self.standards)

        self.roster_headers = [
            "체크",
            "사번", "이름", "성별", "재직",
            "입사일", "퇴사일",
            "근무처", "기숙사", "소개자",
            "은행", "통장번호",
            "보건증만료", "보건증", "통장사본", "여권사본", "근로계약서",
            "서류상태", "수정"
        ]

        self._build_ui()
        self._refresh_all()
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    # ---------------- UI
    def _build_ui(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        self.nb = ttk.Notebook(root)
        self.nb.grid(row=0, column=0, sticky="nsew")

        self.tab_roster = ttk.Frame(self.nb)
        self.tab_status = ttk.Frame(self.nb)
        self.tab_master = ttk.Frame(self.nb)

        self.nb.add(self.tab_roster, text="인력명부")
        self.nb.add(self.tab_status, text="현황")
        self.nb.add(self.tab_master, text="마스터(목록관리)")

        # ===== Tab1: Roster
        self.tab_roster.columnconfigure(0, weight=3)
        self.tab_roster.columnconfigure(1, weight=2)
        self.tab_roster.rowconfigure(0, weight=1)

        left = ttk.Frame(self.tab_roster)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        filter_box = ttk.LabelFrame(left, text="필터/불러오기", padding=10)
        filter_box.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        filter_box.columnconfigure(1, weight=1)
        filter_box.columnconfigure(3, weight=1)

        ttk.Label(filter_box, text="이름").grid(row=0, column=0, sticky="w")
        self.filter_name = tk.StringVar()
        ttk.Entry(filter_box, textvariable=self.filter_name).grid(row=0, column=1, sticky="ew", padx=(6, 12))

        ttk.Label(filter_box, text="근무처").grid(row=0, column=2, sticky="w")
        self.filter_work = tk.StringVar()
        ttk.Entry(filter_box, textvariable=self.filter_work).grid(row=0, column=3, sticky="ew", padx=(6, 12))

        self.filter_missing_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_box, text="서류미비만", variable=self.filter_missing_only,
                        command=self._refresh_all).grid(row=0, column=4, padx=(6, 0), sticky="e")

        ttk.Label(filter_box, text="재직상태").grid(row=0, column=5, sticky="e", padx=(10, 6))
        self.filter_status = tk.StringVar(value="전체")
        ttk.Combobox(filter_box, textvariable=self.filter_status, values=["전체", "재직", "퇴사"],
                     state="readonly", width=6).grid(row=0, column=6, sticky="e")

        ttk.Button(filter_box, text="적용", command=self._refresh_all).grid(row=0, column=7, sticky="e", padx=(10, 0))
        ttk.Button(filter_box, text="초기화", command=self._clear_filter).grid(row=0, column=8, sticky="e", padx=(8, 0))

        ttk.Label(filter_box, text="불러오기(이름/사번)").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.quick_load = tk.StringVar()
        ttk.Entry(filter_box, textvariable=self.quick_load).grid(row=1, column=1, columnspan=3, sticky="ew", padx=(6, 12), pady=(8, 0))
        ttk.Button(filter_box, text="불러오기", command=self._quick_load_record).grid(row=1, column=4, padx=(6, 0), pady=(8, 0), sticky="w")
        ttk.Button(filter_box, text="전체 새로고침", command=self._reload_from_disk).grid(row=1, column=5, columnspan=2, padx=(10, 0), pady=(8, 0), sticky="w")

        action_bar = ttk.Frame(left)
        action_bar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(action_bar, text="체크 전체해제", command=self._clear_checks).pack(side="left")
        ttk.Button(action_bar, text="현황 최신화", command=self._refresh_status).pack(side="left", padx=(8, 0))

        self.sheet = Sheet(left, headers=self.roster_headers, show_x_scrollbar=True, show_y_scrollbar=True)
        self.sheet.grid(row=2, column=0, sticky="nsew")
        self.sheet.enable_bindings((
            "single_select",
            "row_select",
            "arrowkeys",
            "right_click_popup_menu",
            "copy",
            "paste",
            "delete",
            "edit_cell",
            "column_width_resize",
        ))
        self._force_center_align(self.sheet)
        self._apply_column_widths()

        # 클릭 이벤트(버전차 대비)
        self.sheet.extra_bindings([
            ("cell_select", self._on_roster_event),
            ("row_select", self._on_roster_event),
            ("end_edit_cell", self._on_roster_event),
        ])

        # Right form
        right = ttk.Frame(self.tab_roster)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="인력 정보 입력/수정", font=("맑은 고딕", 12, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        form = ttk.Frame(right)
        form.grid(row=1, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        self.v_emp_no = tk.StringVar()
        self.v_name = tk.StringVar()
        self.v_gender = tk.StringVar()
        self.v_status = tk.StringVar(value="재직")
        self.v_hire_date = tk.StringVar()
        self.v_leave_date = tk.StringVar()
        self.v_referrer = tk.StringVar()

        self.v_workplace = tk.StringVar()
        self.v_dorm = tk.StringVar()
        self.v_bank = tk.StringVar()
        self.v_account = tk.StringVar()

        self.v_health_expiry = tk.StringVar()
        self.v_health_file = tk.StringVar()
        self.v_bankbook = tk.StringVar()
        self.v_passport = tk.StringVar()
        self.v_contract = tk.StringVar()

        r = 0
        ttk.Label(form, text="사번", width=10).grid(row=r, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.v_emp_no, state="readonly").grid(row=r, column=1, sticky="ew", pady=6)
        ttk.Button(form, text="자동생성", width=9, command=self._auto_emp_no).grid(row=r, column=2, padx=(6, 0), pady=6)
        ttk.Button(form, text="비우기", width=7, command=lambda: self.v_emp_no.set("")).grid(row=r, column=3, padx=(6, 0), pady=6)
        r += 1

        self._row_text(form, r, "이름*", self.v_name)
        r += 1

        ttk.Label(form, text="성별", width=10).grid(row=r, column=0, sticky="w", pady=6)
        ttk.Combobox(form, textvariable=self.v_gender, values=["", "남", "여", "기타/미표기"],
                     state="readonly").grid(row=r, column=1, columnspan=3, sticky="ew", pady=6)
        r += 1

        ttk.Label(form, text="재직상태", width=10).grid(row=r, column=0, sticky="w", pady=6)
        ttk.Combobox(form, textvariable=self.v_status, values=["재직", "퇴사"],
                     state="readonly").grid(row=r, column=1, columnspan=3, sticky="ew", pady=6)
        r += 1

        self._row_text(form, r, "입사일*", self.v_hire_date)
        r += 1
        self._row_text(form, r, "퇴사일", self.v_leave_date)
        r += 1
        self._row_text(form, r, "소개자", self.v_referrer)
        r += 1

        ttk.Label(form, text="근무처", width=10).grid(row=r, column=0, sticky="w", pady=6)
        self.cb_workplace = ttk.Combobox(form, textvariable=self.v_workplace,
                                         values=self.workplace_names, state="readonly")
        self.cb_workplace.grid(row=r, column=1, columnspan=3, sticky="ew", pady=6)
        r += 1

        ttk.Label(form, text="기숙사", width=10).grid(row=r, column=0, sticky="w", pady=6)
        self.cb_dorm = ttk.Combobox(form, textvariable=self.v_dorm,
                                    values=self.dorm_names, state="readonly")
        self.cb_dorm.grid(row=r, column=1, columnspan=3, sticky="ew", pady=6)
        r += 1

        self._row_text(form, r, "은행", self.v_bank)
        r += 1
        self._row_text(form, r, "통장번호", self.v_account)
        r += 1

        ttk.Label(form, text="보건만료", width=10).grid(row=r, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.v_health_expiry).grid(row=r, column=1, columnspan=3, sticky="ew", pady=6)
        r += 1

        r = self._row_file4(form, r, "보건증", self.v_health_file,
                            lambda: self._pick_to(self.v_health_file, "보건증 선택"),
                            lambda: self._replace_saved_file("health"),
                            lambda: open_file_with_default_app(self.v_health_file.get()),
                            lambda: self.v_health_file.set(""))
        r = self._row_file4(form, r, "통장사본", self.v_bankbook,
                            lambda: self._pick_to(self.v_bankbook, "통장사본 선택"),
                            lambda: self._replace_saved_file("bankbook"),
                            lambda: open_file_with_default_app(self.v_bankbook.get()),
                            lambda: self.v_bankbook.set(""))
        r = self._row_file4(form, r, "여권사본", self.v_passport,
                            lambda: self._pick_to(self.v_passport, "여권사본 선택"),
                            lambda: self._replace_saved_file("passport"),
                            lambda: open_file_with_default_app(self.v_passport.get()),
                            lambda: self.v_passport.set(""))
        r = self._row_file4(form, r, "계약서", self.v_contract,
                            lambda: self._pick_to(self.v_contract, "근로계약서 선택"),
                            lambda: self._replace_saved_file("contract"),
                            lambda: open_file_with_default_app(self.v_contract.get()),
                            lambda: self.v_contract.set(""))

        ttk.Label(right, text="날짜 형식: YYYY-MM-DD (예: 2026-03-15)", foreground="#555").grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )

        btns = ttk.Frame(right)
        btns.grid(row=3, column=0, sticky="ew", pady=(10, 10))
        btns.columnconfigure(0, weight=1)

        ttk.Button(btns, text="신규(입력 초기화)", command=self._clear_form).grid(row=0, column=0, sticky="ew")
        ttk.Button(btns, text="추가 저장", command=self._add_item).grid(row=1, column=0, sticky="ew", pady=6)
        ttk.Button(btns, text="선택 항목 수정 저장", command=self._update_item).grid(row=2, column=0, sticky="ew")
        ttk.Button(btns, text="퇴사 처리(오늘)", command=self._mark_leave_today).grid(row=3, column=0, sticky="ew", pady=6)
        ttk.Button(btns, text="선택/체크 삭제", command=self._delete_item).grid(row=4, column=0, sticky="ew")

        # ===== Tab2: Status
        self.tab_status.columnconfigure(0, weight=1)
        self.tab_status.rowconfigure(0, weight=1)

        status_wrap = ttk.Frame(self.tab_status)
        status_wrap.grid(row=0, column=0, sticky="nsew")
        status_wrap.columnconfigure(0, weight=1)
        status_wrap.columnconfigure(1, weight=1)
        status_wrap.rowconfigure(2, weight=1)

        ttk.Label(status_wrap, text="현황", font=("맑은 고딕", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )

        bar = ttk.Frame(status_wrap)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Button(bar, text="현황 최신화", command=self._refresh_status).pack(side="left")
        ttk.Button(bar, text="퇴사자 목록 보기", command=self._open_leavers_popup).pack(side="left", padx=(8, 0))

        dorm_box = ttk.LabelFrame(status_wrap, text="기숙사 방 현황", padding=10)
        dorm_box.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        dorm_box.columnconfigure(0, weight=1)
        dorm_box.rowconfigure(0, weight=1)

        self.sheet_dorm_rooms = Sheet(
            dorm_box,
            headers=["방", "가용인원", "입주(재직)", "공실", "기숙사비", "입주자(재직 기준)"],
            show_x_scrollbar=False,
            show_y_scrollbar=True
        )
        self.sheet_dorm_rooms.grid(row=0, column=0, sticky="nsew")
        self.sheet_dorm_rooms.enable_bindings(("single_select", "row_select", "arrowkeys"))
        self._force_center_align(self.sheet_dorm_rooms)

        work_box = ttk.LabelFrame(status_wrap, text="근무처 현황", padding=10)
        work_box.grid(row=2, column=1, sticky="nsew")
        work_box.columnconfigure(0, weight=1)
        work_box.rowconfigure(0, weight=1)

        self.sheet_work = Sheet(
            work_box,
            headers=["근무처", "총인원", "재직", "필요인원", "부족(필요-재직)", "퇴사"],
            show_x_scrollbar=False,
            show_y_scrollbar=True
        )
        self.sheet_work.grid(row=0, column=0, sticky="nsew")
        self.sheet_work.enable_bindings(("single_select", "row_select", "arrowkeys"))
        self._force_center_align(self.sheet_work)

        # ===== Tab3: Master
        self.tab_master.columnconfigure(0, weight=1)
        self.tab_master.columnconfigure(1, weight=1)
        self.tab_master.rowconfigure(1, weight=1)

        top_bar = ttk.Frame(self.tab_master, padding=10)
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew")

        ttk.Label(top_bar, text="표준 목록 관리 (추가/삭제/수정 후 저장)", font=("맑은 고딕", 11, "bold")).pack(side="left")

        btn_wrap = ttk.Frame(top_bar)
        btn_wrap.pack(side="right")
        ttk.Button(btn_wrap, text="근무처 행 추가", command=self._master_add_workplace).pack(side="left", padx=(0, 6))
        ttk.Button(btn_wrap, text="근무처 행 삭제", command=self._master_delete_workplace).pack(side="left", padx=(0, 12))
        ttk.Button(btn_wrap, text="기숙사 행 추가", command=self._master_add_dorm).pack(side="left", padx=(0, 6))
        ttk.Button(btn_wrap, text="기숙사 행 삭제", command=self._master_delete_dorm).pack(side="left", padx=(0, 12))
        ttk.Button(btn_wrap, text="저장", command=self._save_master_lists).pack(side="left")

        left_box = ttk.LabelFrame(self.tab_master, text="근무처 목록 (필요인원 포함)", padding=10)
        left_box.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))
        left_box.columnconfigure(0, weight=1)
        left_box.rowconfigure(0, weight=1)

        right_box = ttk.LabelFrame(self.tab_master, text="기숙사 목록 (가용인원/기숙사비 포함)", padding=10)
        right_box.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))
        right_box.columnconfigure(0, weight=1)
        right_box.rowconfigure(0, weight=1)

        self.sheet_master_work = Sheet(left_box, headers=["근무처명", "필요인원"], show_x_scrollbar=False, show_y_scrollbar=True)
        self.sheet_master_work.grid(row=0, column=0, sticky="nsew")
        self.sheet_master_work.enable_bindings(("single_select", "row_select", "arrowkeys", "edit_cell", "paste", "delete"))
        self._force_center_align(self.sheet_master_work)

        self.sheet_master_dorm = Sheet(right_box, headers=["기숙사", "가용인원", "기숙사비"], show_x_scrollbar=False, show_y_scrollbar=True)
        self.sheet_master_dorm.grid(row=0, column=0, sticky="nsew")
        self.sheet_master_dorm.enable_bindings(("single_select", "row_select", "arrowkeys", "edit_cell", "paste", "delete"))
        self._force_center_align(self.sheet_master_dorm)

        self._refresh_master_sheets()

    # ---------------- Alignment
    def _force_center_align(self, sheet: Sheet):
        for fn in (
            lambda: sheet.align_headers("center"),
            lambda: sheet.align_columns("center"),
            lambda: sheet.set_options(table_align="center"),
            lambda: sheet.set_options(header_align="center"),
            lambda: sheet.set_options(cell_align="center"),
            lambda: sheet.set_options(default_alignment="center"),
        ):
            try:
                fn()
            except Exception:
                pass

    def _apply_column_widths(self):
        widths = [
            55,  # 체크
            95, 90, 60, 60,
            95, 95,
            150, 130, 120,
            85, 140,
            110, 70, 70, 70, 80,
            70, 150,
        ]
        try:
            self.sheet.set_column_widths(widths)
        except Exception:
            for i, w in enumerate(widths):
                try:
                    self.sheet.set_column_width(i, w)
                except Exception:
                    pass

    # ---------------- small UI helpers
    def _row_text(self, parent, row, label, var):
        ttk.Label(parent, text=label, width=10).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, columnspan=3, sticky="ew", pady=6)

    def _row_file4(self, parent, row, label, var, pick_cmd, load_cmd, open_cmd, clear_cmd):
        ttk.Label(parent, text=label, width=10).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=var, state="readonly").grid(row=row, column=1, sticky="ew", pady=6)
        ttk.Button(parent, text="선택", width=6, command=pick_cmd).grid(row=row, column=2, padx=(6, 0), pady=6)
        ttk.Button(parent, text="불러오기", width=7, command=load_cmd).grid(row=row, column=3, padx=(6, 0), pady=6)
        ttk.Button(parent, text="열기", width=6, command=open_cmd).grid(row=row, column=4, padx=(6, 0), pady=6)
        ttk.Button(parent, text="지우기", width=6, command=clear_cmd).grid(row=row, column=5, padx=(6, 0), pady=6)
        return row + 1

    # ---------------- Tab changed
    def _on_tab_changed(self, _evt=None):
        try:
            tab_text = self.nb.tab(self.nb.select(), "text")
        except Exception:
            return
        if tab_text == "현황":
            self._refresh_status()

    # ---------------- Filters
    def _clear_filter(self):
        self.filter_name.set("")
        self.filter_work.set("")
        self.filter_missing_only.set(False)
        self.filter_status.set("전체")
        self._refresh_all()

    # ---------------- File pick
    def _pick_to(self, var, title):
        p = filedialog.askopenfilename(
            title=title,
            filetypes=[("문서/이미지/PDF", "*.png;*.jpg;*.jpeg;*.webp;*.pdf;*.heic;*.doc;*.docx"), ("모든 파일", "*.*")]
        )
        if p:
            var.set(p)

    # ---------------- Auto emp no
    def _auto_emp_no(self):
        hd = norm(self.v_hire_date.get())
        eno = generate_emp_no(self.items, hd)
        if not eno:
            messagebox.showwarning("확인", "입사일(YYYY-MM-DD)을 먼저 입력하세요.")
            return
        self.v_emp_no.set(eno)

    # ============================
    # 클릭/체크/불러오기
    # ============================
    def _get_row_col_from_any_event(self, event):
        r = None
        c = None

        if isinstance(event, dict):
            r = event.get("row", None)
            c = event.get("column", None)

        if r is None or c is None:
            try:
                sel = self.sheet.get_currently_selected()
                if isinstance(sel, (list, tuple)):
                    if len(sel) == 2 and all(isinstance(x, int) for x in sel):
                        r, c = sel
                    elif len(sel) > 0 and isinstance(sel[0], (list, tuple)) and len(sel[0]) >= 2:
                        r, c = sel[0][0], sel[0][1]
            except Exception:
                pass

        return r, c

    def _on_roster_event(self, event):
        r, c = self._get_row_col_from_any_event(event)
        if r is None or r < 0 or r >= len(self.row_id_map):
            return
        rec_id = self.row_id_map[r]

        # 0번 칼럼 = 체크
        if c == 0:
            self._toggle_check(rec_id)
            self._set_selected(rec_id)
            return

        self._set_selected(rec_id)

    def _set_selected(self, rec_id: str):
        self.selected_id = rec_id
        self._load_record_to_form(rec_id)
        self._refresh_roster()

    def _toggle_check(self, rec_id: str):
        if rec_id in self.checked_ids:
            self.checked_ids.remove(rec_id)
        else:
            self.checked_ids.add(rec_id)

    def _load_record_to_form(self, rec_id: str):
        rec = next((x for x in self.items if x["id"] == rec_id), None)
        if not rec:
            return

        self.v_emp_no.set(rec.get("emp_no", ""))
        self.v_name.set(rec.get("name", ""))
        self.v_gender.set(rec.get("gender", ""))
        self.v_status.set(rec.get("employment_status", "재직"))
        self.v_hire_date.set(rec.get("hire_date", ""))
        self.v_leave_date.set(rec.get("leave_date", ""))
        self.v_referrer.set(rec.get("referrer", ""))

        self.v_workplace.set(rec.get("workplace", ""))
        self.v_dorm.set(rec.get("dorm", ""))
        self.v_bank.set(rec.get("bank", ""))
        self.v_account.set(rec.get("account_no", ""))

        self.v_health_expiry.set(rec.get("health_expiry", ""))
        self.v_health_file.set(rec.get("health_file_path", ""))
        self.v_bankbook.set(rec.get("bankbook_path", ""))
        self.v_passport.set(rec.get("passport_path", ""))
        self.v_contract.set(rec.get("contract_path", ""))

    # ---------------- Quick load
    def _quick_load_record(self):
        key = norm(self.quick_load.get())
        if not key:
            messagebox.showwarning("확인", "불러오기(이름/사번)를 입력하세요.")
            return

        self.items = load_db()

        target = None
        for rec in self.items:
            if norm(rec.get("emp_no")) == key:
                target = rec
                break
        if target is None:
            for rec in self.items:
                if norm(rec.get("name")) == key:
                    target = rec
                    break
        if target is None:
            for rec in self.items:
                if key in norm(rec.get("name")):
                    target = rec
                    break

        if target is None:
            messagebox.showwarning("확인", f"찾을 수 없습니다: {key}")
            return

        self._select_record_in_roster(target["id"])

    def _select_record_in_roster(self, rec_id: str):
        self.nb.select(self.tab_roster)
        self._refresh_all()
        try:
            idx = self.row_id_map.index(rec_id)
        except ValueError:
            idx = None
        if idx is not None:
            try:
                self.sheet.select_row(idx, redraw=True)
            except Exception:
                pass
        self._set_selected(rec_id)

    def _reload_from_disk(self):
        self.items = load_db()
        self._refresh_all()
        messagebox.showinfo("완료", "데이터 새로고침 완료")

    def _clear_checks(self):
        self.checked_ids = set()
        self._refresh_roster()

    # ---------------- Missing docs
    def _missing_docs(self, rec):
        miss = []
        if not norm(rec.get("health_file_path")):
            miss.append("보건증")
        if not norm(rec.get("bankbook_path")):
            miss.append("통장")
        if not norm(rec.get("passport_path")):
            miss.append("여권")
        if not norm(rec.get("contract_path")):
            miss.append("계약서")
        return miss

    # ---------------- CRUD
    def _clear_form(self):
        self.selected_id = None
        self.v_emp_no.set("")
        self.v_name.set("")
        self.v_gender.set("")
        self.v_status.set("재직")
        self.v_hire_date.set("")
        self.v_leave_date.set("")
        self.v_referrer.set("")
        self.v_workplace.set("")
        self.v_dorm.set("")
        self.v_bank.set("")
        self.v_account.set("")
        self.v_health_expiry.set("")
        self.v_health_file.set("")
        self.v_bankbook.set("")
        self.v_passport.set("")
        self.v_contract.set("")

    def _validate(self):
        if not norm(self.v_name.get()):
            messagebox.showwarning("확인", "이름은 필수입니다.")
            return False

        hd = parse_yyyy_mm_dd(self.v_hire_date.get())
        if hd in (None, "invalid"):
            messagebox.showwarning("확인", "입사일은 필수이며 형식은 YYYY-MM-DD 입니다.")
            return False

        ld = parse_yyyy_mm_dd(self.v_leave_date.get())
        if ld == "invalid":
            messagebox.showwarning("확인", "퇴사일 형식이 잘못되었습니다. YYYY-MM-DD")
            return False

        he = parse_yyyy_mm_dd(self.v_health_expiry.get())
        if he == "invalid":
            messagebox.showwarning("확인", "보건증 만료일 형식이 잘못되었습니다. YYYY-MM-DD")
            return False

        if norm(self.v_workplace.get()) and self.v_workplace.get() not in self.workplace_names:
            messagebox.showwarning("확인", "근무처는 표준 목록에서 선택해야 합니다.")
            return False
        if norm(self.v_dorm.get()) and self.v_dorm.get() not in self.dorm_names:
            messagebox.showwarning("확인", "기숙사는 표준 목록에서 선택해야 합니다.")
            return False

        if norm(self.v_status.get()) == "퇴사" and not norm(self.v_leave_date.get()):
            ok = messagebox.askyesno("확인", "재직상태가 '퇴사'인데 퇴사일이 비어있습니다. 그대로 저장할까요?")
            if not ok:
                return False

        return True

    def _store_file(self, path_in: str, folder: str, name: str, kind: str) -> str:
        p = norm(path_in)
        if not p:
            return ""
        if os.path.isabs(p):
            return copy_to_upload(p, folder, name, kind)
        return p

    def _emp_no_unique(self, emp_no: str, exclude_id: str = "") -> bool:
        emp_no = norm(emp_no)
        if not emp_no:
            return True
        for r in self.items:
            if exclude_id and r.get("id") == exclude_id:
                continue
            if norm(r.get("emp_no")) == emp_no:
                return False
        return True

    def _add_item(self):
        if not self._validate():
            return

        name = norm(self.v_name.get())
        emp_no = norm(self.v_emp_no.get()) or generate_emp_no(self.items, self.v_hire_date.get())
        if not emp_no:
            messagebox.showwarning("확인", "사번 생성 실패(입사일 확인)")
            return
        if not self._emp_no_unique(emp_no):
            messagebox.showwarning("확인", f"사번 중복입니다: {emp_no}")
            return

        rec = {
            "id": uuid.uuid4().hex,
            "emp_no": emp_no,
            "name": name,
            "gender": norm(self.v_gender.get()),
            "employment_status": norm(self.v_status.get()) or "재직",
            "hire_date": norm(self.v_hire_date.get()),
            "leave_date": norm(self.v_leave_date.get()),
            "referrer": norm(self.v_referrer.get()),
            "workplace": norm(self.v_workplace.get()),
            "dorm": norm(self.v_dorm.get()),
            "bank": norm(self.v_bank.get()),
            "account_no": norm(self.v_account.get()),
            "health_expiry": norm(self.v_health_expiry.get()),
            "health_file_path": self._store_file(self.v_health_file.get(), HEALTH_DIR, name, "health"),
            "bankbook_path": self._store_file(self.v_bankbook.get(), BANKBOOK_DIR, name, "bankbook"),
            "passport_path": self._store_file(self.v_passport.get(), PASSPORT_DIR, name, "passport"),
            "contract_path": self._store_file(self.v_contract.get(), CONTRACT_DIR, name, "contract"),
            "created_at": now_str(),
            "updated_at": now_str(),
        }

        self.items.append(rec)
        save_db(self.items)

        self._refresh_all()
        self._select_record_in_roster(rec["id"])
        messagebox.showinfo("완료", "추가 저장 완료")

    def _update_item(self):
        if not self.selected_id:
            messagebox.showwarning("확인", "왼쪽 표에서 사람을 클릭해 불러온 뒤 수정하세요.")
            return
        if not self._validate():
            return

        rec = next((x for x in self.items if x["id"] == self.selected_id), None)
        if not rec:
            return

        name = norm(self.v_name.get())
        emp_no = norm(self.v_emp_no.get()) or generate_emp_no(self.items, self.v_hire_date.get())
        if not emp_no:
            messagebox.showwarning("확인", "사번 생성 실패(입사일 확인)")
            return
        if not self._emp_no_unique(emp_no, exclude_id=self.selected_id):
            messagebox.showwarning("확인", f"사번 중복입니다: {emp_no}")
            return

        rec["emp_no"] = emp_no
        rec["name"] = name
        rec["gender"] = norm(self.v_gender.get())
        rec["employment_status"] = norm(self.v_status.get()) or "재직"
        rec["hire_date"] = norm(self.v_hire_date.get())
        rec["leave_date"] = norm(self.v_leave_date.get())
        rec["referrer"] = norm(self.v_referrer.get())
        rec["workplace"] = norm(self.v_workplace.get())
        rec["dorm"] = norm(self.v_dorm.get())
        rec["bank"] = norm(self.v_bank.get())
        rec["account_no"] = norm(self.v_account.get())
        rec["health_expiry"] = norm(self.v_health_expiry.get())
        rec["health_file_path"] = self._store_file(self.v_health_file.get(), HEALTH_DIR, name, "health")
        rec["bankbook_path"] = self._store_file(self.v_bankbook.get(), BANKBOOK_DIR, name, "bankbook")
        rec["passport_path"] = self._store_file(self.v_passport.get(), PASSPORT_DIR, name, "passport")
        rec["contract_path"] = self._store_file(self.v_contract.get(), CONTRACT_DIR, name, "contract")
        rec["updated_at"] = now_str()

        save_db(self.items)
        self._refresh_all()
        self._select_record_in_roster(rec["id"])
        messagebox.showinfo("완료", "수정 저장 완료")

    def _get_target_ids(self):
        if self.checked_ids:
            return [rid for rid in self.checked_ids if any(x["id"] == rid for x in self.items)]
        if self.selected_id:
            return [self.selected_id]
        return []

    def _mark_leave_today(self):
        target_ids = self._get_target_ids()
        if not target_ids:
            messagebox.showwarning("확인", "체크(■) 또는 표 클릭 후 퇴사 처리하세요.")
            return

        updated = 0
        for rid in target_ids:
            rec = next((x for x in self.items if x["id"] == rid), None)
            if not rec:
                continue
            rec["employment_status"] = "퇴사"
            if not norm(rec.get("leave_date")):
                rec["leave_date"] = today_str()
            rec["updated_at"] = now_str()
            updated += 1

        save_db(self.items)
        self.checked_ids = set()
        self._refresh_all()
        if self.selected_id:
            self._load_record_to_form(self.selected_id)
        messagebox.showinfo("완료", f"퇴사 처리 완료: {updated}명")

    def _delete_item(self):
        target_ids = self._get_target_ids()
        if not target_ids:
            messagebox.showwarning("확인", "체크(■) 또는 표 클릭 후 삭제하세요.")
            return
        ok = messagebox.askyesno("삭제", f"선택 항목 {len(target_ids)}개를 삭제할까요?")
        if not ok:
            return
        self.items = [x for x in self.items if x["id"] not in set(target_ids)]
        save_db(self.items)
        self.checked_ids = set()
        self.selected_id = None
        self._refresh_all()
        self._clear_form()
        messagebox.showinfo("완료", "삭제 완료")

    # ---------------- Replace saved file
    def _replace_saved_file(self, kind: str):
        if not self.selected_id:
            messagebox.showwarning("확인", "먼저 표에서 사람을 클릭해 불러오세요.")
            return
        rec = next((x for x in self.items if x["id"] == self.selected_id), None)
        if not rec:
            return

        name = norm(rec.get("name"))
        if not name:
            messagebox.showwarning("확인", "이름이 비어있습니다. 먼저 이름 저장하세요.")
            return

        title_map = {
            "health": "보건증 선택",
            "bankbook": "통장사본 선택",
            "passport": "여권사본 선택",
            "contract": "근로계약서 선택",
        }
        folder_map = {
            "health": HEALTH_DIR,
            "bankbook": BANKBOOK_DIR,
            "passport": PASSPORT_DIR,
            "contract": CONTRACT_DIR,
        }
        key_map = {
            "health": "health_file_path",
            "bankbook": "bankbook_path",
            "passport": "passport_path",
            "contract": "contract_path",
        }
        var_map = {
            "health": self.v_health_file,
            "bankbook": self.v_bankbook,
            "passport": self.v_passport,
            "contract": self.v_contract,
        }

        p = filedialog.askopenfilename(
            title=title_map.get(kind, "파일 선택"),
            filetypes=[("문서/이미지/PDF", "*.png;*.jpg;*.jpeg;*.webp;*.pdf;*.heic;*.doc;*.docx"), ("모든 파일", "*.*")]
        )
        if not p:
            return

        rel = copy_to_upload(p, folder_map[kind], name, kind)
        rec[key_map[kind]] = rel
        rec["updated_at"] = now_str()
        save_db(self.items)

        var_map[kind].set(rel)
        self._refresh_all()
        messagebox.showinfo("완료", "파일 불러오기(교체) 완료")

    # ---------------- Master list
    def _refresh_master_sheets(self):
        wp_rows = []
        for w in self.standards.get("workplaces") or []:
            wp_rows.append([norm(w.get("name")), safe_int(w.get("need", 0), 0)])

        dorm_rows = []
        for r in self.standards.get("dorms") or []:
            dorm_rows.append([norm(r.get("name")), safe_int(r.get("capacity", 0), 0), safe_int(r.get("fee", 0), 0)])

        self.sheet_master_work.set_sheet_data(wp_rows)
        self.sheet_master_dorm.set_sheet_data(dorm_rows)
        try:
            self.sheet_master_work.set_column_widths([320, 100])
            self.sheet_master_dorm.set_column_widths([260, 100, 120])
        except Exception:
            pass

    def _read_master_workplaces(self):
        try:
            data = self.sheet_master_work.get_sheet_data(return_copy=True)
        except Exception:
            data = self.sheet_master_work.get_sheet_data()
        out = []
        for row in data:
            if not row:
                continue
            name = norm(row[0]) if len(row) > 0 else ""
            if not name:
                continue
            need = safe_int(row[1] if len(row) > 1 else 0, 0)
            out.append({"name": name, "need": need})
        return out

    def _read_master_dorms(self):
        try:
            data = self.sheet_master_dorm.get_sheet_data(return_copy=True)
        except Exception:
            data = self.sheet_master_dorm.get_sheet_data()
        out = []
        for row in data:
            if not row:
                continue
            name = norm(row[0]) if len(row) > 0 else ""
            if not name:
                continue
            cap = safe_int(row[1] if len(row) > 1 else 0, 0)
            fee = safe_int(row[2] if len(row) > 2 else 0, 0)
            out.append({"name": name, "capacity": cap, "fee": fee})
        return out

    def _apply_standards_to_ui(self):
        self.workplace_names = standards_workplace_names(self.standards)
        self.dorm_names = standards_dorm_names(self.standards)

        self.cb_workplace.configure(values=self.workplace_names)
        self.cb_dorm.configure(values=self.dorm_names)

        if norm(self.v_workplace.get()) and self.v_workplace.get() not in self.workplace_names:
            self.v_workplace.set("")
        if norm(self.v_dorm.get()) and self.v_dorm.get() not in self.dorm_names:
            self.v_dorm.set("")

    def _save_master_lists(self):
        workplaces = self._read_master_workplaces()
        dorms = self._read_master_dorms()

        save_standards(workplaces, dorms)
        self.standards = load_standards()
        self._apply_standards_to_ui()
        self._refresh_master_sheets()
        self._refresh_all()
        messagebox.showinfo("완료", "마스터 저장 완료 (드롭다운/현황 반영)")

    def _master_add_workplace(self):
        try:
            data = self.sheet_master_work.get_sheet_data(return_copy=True)
        except Exception:
            data = self.sheet_master_work.get_sheet_data()
        data.append(["", 0])
        self.sheet_master_work.set_sheet_data(data)

    def _master_add_dorm(self):
        try:
            data = self.sheet_master_dorm.get_sheet_data(return_copy=True)
        except Exception:
            data = self.sheet_master_dorm.get_sheet_data()
        data.append(["", 0, 0])
        self.sheet_master_dorm.set_sheet_data(data)

    def _get_selected_rows_safe(self, sheet: Sheet):
        rows = set()
        for getter in (
            lambda: sheet.get_selected_rows(),
            lambda: sheet.get_selected_row(),
            lambda: sheet.get_currently_selected(),
            lambda: sheet.get_selected_cells(),
        ):
            try:
                sel = getter()
            except Exception:
                continue
            if sel is None:
                continue
            if isinstance(sel, int):
                if sel >= 0:
                    rows.add(sel)
            elif isinstance(sel, (list, tuple, set)):
                for it in sel:
                    if isinstance(it, int):
                        if it >= 0:
                            rows.add(it)
                    elif isinstance(it, (list, tuple)) and len(it) >= 2:
                        r = it[0]
                        if isinstance(r, int) and r >= 0:
                            rows.add(r)
        return sorted(rows)

    def _master_delete_workplace(self):
        rows = self._get_selected_rows_safe(self.sheet_master_work)
        if not rows:
            messagebox.showwarning("확인", "삭제할 근무처 행을 선택하세요.")
            return
        try:
            data = self.sheet_master_work.get_sheet_data(return_copy=True)
        except Exception:
            data = self.sheet_master_work.get_sheet_data()
        keep = [row for i, row in enumerate(data) if i not in set(rows)]
        self.sheet_master_work.set_sheet_data(keep)

    def _master_delete_dorm(self):
        rows = self._get_selected_rows_safe(self.sheet_master_dorm)
        if not rows:
            messagebox.showwarning("확인", "삭제할 기숙사 행을 선택하세요.")
            return
        try:
            data = self.sheet_master_dorm.get_sheet_data(return_copy=True)
        except Exception:
            data = self.sheet_master_dorm.get_sheet_data()
        keep = [row for i, row in enumerate(data) if i not in set(rows)]
        self.sheet_master_dorm.set_sheet_data(keep)

    # ---------------- leavers popup
    def _open_leavers_popup(self):
        win = tk.Toplevel(self)
        win.title("퇴사자 목록")
        win.geometry("1000x520")
        win.minsize(900, 420)

        wrap = ttk.Frame(win, padding=10)
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(1, weight=1)

        ttk.Label(wrap, text="퇴사자 목록 (행 클릭 → 명부에서 불러오기)", font=("맑은 고딕", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        headers = ["사번", "이름", "입사일", "퇴사일", "근무처", "기숙사"]
        sheet = Sheet(wrap, headers=headers, show_x_scrollbar=True, show_y_scrollbar=True)
        sheet.grid(row=1, column=0, sticky="nsew")
        sheet.enable_bindings(("single_select", "row_select", "arrowkeys"))
        self._force_center_align(sheet)

        rows = []
        id_map = []
        for rec in self.items:
            if norm(rec.get("employment_status", "재직")) != "퇴사":
                continue
            rows.append([
                norm(rec.get("emp_no")),
                norm(rec.get("name")),
                norm(rec.get("hire_date")),
                norm(rec.get("leave_date")),
                norm(rec.get("workplace")) or "(미입력)",
                norm(rec.get("dorm")) or "(미입력)",
            ])
            id_map.append(rec["id"])

        sheet.set_sheet_data(rows)

        def on_select(evt):
            rr = None
            if isinstance(evt, dict):
                rr = evt.get("row", None)
            if rr is None:
                return
            if rr < 0 or rr >= len(id_map):
                return
            self._select_record_in_roster(id_map[rr])
            win.lift()

        sheet.extra_bindings([("cell_select", on_select)])

    # ---------------- Refresh
    def _refresh_all(self):
        self._refresh_roster()
        self._refresh_status()

    def _refresh_roster(self):
        qn = norm(self.filter_name.get())
        qw = norm(self.filter_work.get())
        missing_only = bool(self.filter_missing_only.get())
        status_filter = norm(self.filter_status.get())

        def match(rec):
            if qn and qn not in norm(rec.get("name")):
                return False
            if qw and qw not in norm(rec.get("workplace")):
                return False
            if missing_only and (len(self._missing_docs(rec)) == 0):
                return False
            if status_filter in ("재직", "퇴사") and norm(rec.get("employment_status", "재직")) != status_filter:
                return False
            return True

        table = []
        self.row_id_map = []
        self.sheet.set_sheet_data([])

        for rec in self.items:
            if not match(rec):
                continue

            missing = self._missing_docs(rec)
            doc_txt = "미비" if missing else "정상"

            exp = norm(rec.get("health_expiry"))
            flag = health_expiry_flag(exp)
            if flag == "expired" and exp:
                exp_cell = f"만료 {exp}"
            elif flag == "soon" and exp:
                exp_cell = f"임박 {exp}"
            elif flag == "invalid" and exp:
                exp_cell = "형식오류"
            else:
                exp_cell = exp

            def cell_file(path):
                return short_file(path) if path else "미비"

            chk_box = self.BOX_ON if rec["id"] in self.checked_ids else self.BOX_OFF

            row = [
                chk_box,
                norm(rec.get("emp_no")),
                norm(rec.get("name")),
                norm(rec.get("gender")),
                norm(rec.get("employment_status", "재직")),
                norm(rec.get("hire_date")),
                norm(rec.get("leave_date")),
                norm(rec.get("workplace")) or "(미입력)",
                norm(rec.get("dorm")) or "(미입력)",
                norm(rec.get("referrer")),
                norm(rec.get("bank")),
                norm(rec.get("account_no")),
                exp_cell,
                cell_file(norm(rec.get("health_file_path"))),
                cell_file(norm(rec.get("bankbook_path"))),
                cell_file(norm(rec.get("passport_path"))),
                cell_file(norm(rec.get("contract_path"))),
                doc_txt,
                norm(rec.get("updated_at")),
            ]
            table.append(row)
            self.row_id_map.append(rec["id"])

        self.sheet.set_sheet_data(table)
        self._force_center_align(self.sheet)
        self._apply_column_widths()

        RED = "#d40000"
        ORANGE = "#c06000"
        try:
            self.sheet.dehighlight_all()
        except Exception:
            pass

        COL_HEALTH_EXP = 12
        COL_DOC_STATUS = 17

        for rr, row in enumerate(table):
            for cc, val in enumerate(row):
                if isinstance(val, str) and val.strip() == "미비":
                    try:
                        self.sheet.highlight_cells(row=rr, column=cc, fg=RED)
                    except Exception:
                        pass
            if row[COL_DOC_STATUS] == "미비":
                try:
                    self.sheet.highlight_cells(row=rr, column=COL_DOC_STATUS, fg=RED)
                except Exception:
                    pass

            exp_text = row[COL_HEALTH_EXP]
            if isinstance(exp_text, str):
                if exp_text.startswith("만료") or exp_text == "형식오류":
                    try:
                        self.sheet.highlight_cells(row=rr, column=COL_HEALTH_EXP, fg=RED)
                    except Exception:
                        pass
                elif exp_text.startswith("임박"):
                    try:
                        self.sheet.highlight_cells(row=rr, column=COL_HEALTH_EXP, fg=ORANGE)
                    except Exception:
                        pass

    def _refresh_status(self):
        # standards 최신 반영
        self.standards = load_standards()
        self._apply_standards_to_ui()
        need_map = standards_need_map(self.standards)
        dorm_map = standards_dorm_map(self.standards)

        # 1) 기숙사 현황
        room_rows = []
        for dorm_name in [x for x in self.dorm_names if x]:
            cap = safe_int((dorm_map.get(dorm_name) or {}).get("capacity", 0), 0)
            fee = safe_int((dorm_map.get(dorm_name) or {}).get("fee", 0), 0)

            occupants = [
                norm(r.get("name")) for r in self.items
                if norm(r.get("employment_status", "재직")) == "재직"
                and norm(r.get("dorm")) == dorm_name
            ]
            used = len([x for x in occupants if x])
            empty = max(cap - used, 0) if cap > 0 else ""

            room_rows.append([
                dorm_name,
                cap,
                used,
                empty,
                fee,
                ", ".join([x for x in occupants if x])
            ])

        self.sheet_dorm_rooms.set_sheet_data(room_rows)
        self._force_center_align(self.sheet_dorm_rooms)
        try:
            self.sheet_dorm_rooms.set_column_widths([170, 80, 80, 70, 90, 460])
        except Exception:
            pass

        # 2) 근무처 현황
        counts = {}
        for rec in self.items:
            wp = norm(rec.get("workplace")) or "(미입력)"
            st = norm(rec.get("employment_status", "재직"))
            if wp not in counts:
                counts[wp] = {"재직": 0, "퇴사": 0}
            if st == "퇴사":
                counts[wp]["퇴사"] += 1
            else:
                counts[wp]["재직"] += 1

        for std_wp in [w["name"] for w in (self.standards.get("workplaces") or [])]:
            if std_wp and std_wp not in counts:
                counts[std_wp] = {"재직": 0, "퇴사": 0}

        work_rows = []
        for wp, d in sorted(counts.items(), key=lambda x: (-(x[1]["재직"] + x[1]["퇴사"]), x[0])):
            total = d["재직"] + d["퇴사"]
            need = safe_int(need_map.get(wp, 0), 0)
            lack = need - d["재직"]
            work_rows.append([wp, total, d["재직"], need, lack, d["퇴사"]])

        self.sheet_work.set_sheet_data(work_rows)
        self._force_center_align(self.sheet_work)
        try:
            self.sheet_work.set_column_widths([260, 80, 70, 80, 120, 70])
        except Exception:
            pass


if __name__ == "__main__":
    app = RosterApp()
    app.mainloop()
