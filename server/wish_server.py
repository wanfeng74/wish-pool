#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
许愿池 · Wish Pool Server

面向有道词典笔的愿望收集服务：提交愿望 / 全员可见 / +1 支持 / 按支持度排序 / 实时推送。

零第三方依赖，仅使用 Python 3 标准库（http.server + sqlite3 + threading）。

环境变量：
    PORT            监听端口，默认 17613
    HOST            监听地址，默认 0.0.0.0
    DB_PATH         SQLite 路径，默认 ./wish.db
    LOG_PATH        日志路径，默认 ./wish.log
    ADMIN_PASS      管理密码；默认随机生成并写入 admin_pass.txt
    PANEL_PATH      panel.html 路径，默认与脚本同目录
    MAX_BODY        单次请求体上限（字节），默认 64KB
    RATE_WINDOW_S   限流窗口（秒），默认 60
    RATE_SUBMIT     每窗口每 IP 最多提交数，默认 20
    RATE_VOTE       每窗口每 IP 最多 +1 数，默认 240
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HOST = os.environ.get("HOST", "0.0.0.0")
PORT_SPEC = os.environ.get("PORT", "17613")


def parse_ports(spec):
    """支持 "17613" 或 "32894,17613" 多端口写法。"""
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        if part.isdigit() and 0 < int(part) <= 65535:
            out.append(int(part))
    return out or [17613]


PORTS = parse_ports(PORT_SPEC)
PORT = PORTS[0]
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "wish.db"))
LOG_PATH = os.environ.get("LOG_PATH", os.path.join(BASE_DIR, "wish.log"))
PANEL_PATH = os.environ.get("PANEL_PATH", os.path.join(BASE_DIR, "panel.html"))
PKG_DIR = os.environ.get("PKG_DIR", os.path.join(BASE_DIR, "pkg"))
MAX_BODY = int(os.environ.get("MAX_BODY", str(64 * 1024)))
RATE_WINDOW_S = int(os.environ.get("RATE_WINDOW_S", "60"))
RATE_SUBMIT = int(os.environ.get("RATE_SUBMIT", "20"))
RATE_VOTE = int(os.environ.get("RATE_VOTE", "240"))
RATE_CLAIM = int(os.environ.get("RATE_CLAIM", "60"))

MAX_TITLE = 40          # 愿望标题最大字数
MAX_DESC = 300          # 愿望描述最大字数
MAX_NICK = 20           # 昵称最大字数
MAX_PKG = 16 * 1024 * 1024   # 安装包上传上限 16MB

# 愿望分类：id -> 展示名 / 颜色
CATEGORIES = [
    {"id": "app",   "name": "想要新App", "color": "#5B8CFF"},
    {"id": "feat",  "name": "功能增强",   "color": "#22D3B8"},
    {"id": "game",  "name": "游戏相关",   "color": "#A855F7"},
    {"id": "read",  "name": "阅读学习",   "color": "#FFB020"},
    {"id": "system","name": "系统体验",   "color": "#FF6B8A"},
    {"id": "other", "name": "其它想法",   "color": "#8B95B0"},
]
CATEGORY_IDS = {c["id"] for c in CATEGORIES}

# 愿望状态：服务端可调整，客户端只读展示
#   open     待认领（默认）
#   doing    开发中
#   done     已上线
#   rejected 暂不做
STATUSES = [
    {"id": "open",     "name": "待认领", "color": "#8B95B0"},
    {"id": "doing",    "name": "开发中", "color": "#5B8CFF"},
    {"id": "done",     "name": "已上线", "color": "#22D3B8"},
    {"id": "rejected", "name": "暂不做", "color": "#6C7794"},
]
STATUS_IDS = {s["id"] for s in STATUSES}

log = logging.getLogger("wish")


def _setup_logging():
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)


# --------------------------------------------------------------------------
# 数据库
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS wishes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    desc        TEXT    NOT NULL DEFAULT '',
    category    TEXT    NOT NULL DEFAULT 'other',
    nick        TEXT    NOT NULL DEFAULT '',
    sn          TEXT    NOT NULL DEFAULT '',
    votes       INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL,
    deleted     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_wishes_votes ON wishes(deleted, votes DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_wishes_new   ON wishes(deleted, id DESC);

CREATE TABLE IF NOT EXISTS votes (
    wish_id     INTEGER NOT NULL,
    voter       TEXT    NOT NULL,
    created_at  INTEGER NOT NULL,
    PRIMARY KEY (wish_id, voter)
);
CREATE INDEX IF NOT EXISTS idx_votes_voter ON votes(voter);

CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);

-- 认领审计日志：每次认领/释放都留痕，昵称由服务端记录
CREATE TABLE IF NOT EXISTS claims (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    wish_id     INTEGER NOT NULL,
    nick        TEXT    NOT NULL,
    voter       TEXT    NOT NULL,
    sn          TEXT    NOT NULL DEFAULT '',
    created_at  INTEGER NOT NULL,
    released_at INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_claims_wish ON claims(wish_id, released_at);
CREATE INDEX IF NOT EXISTS idx_claims_voter ON claims(voter);

-- 客户端日志上报：笔端排查用
CREATE TABLE IF NOT EXISTS client_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sn          TEXT    NOT NULL DEFAULT '',
    client_id   TEXT    NOT NULL DEFAULT '',
    version     TEXT    NOT NULL DEFAULT '',
    level       TEXT    NOT NULL DEFAULT 'info',
    msg         TEXT    NOT NULL DEFAULT '',
    created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_sn ON client_logs(sn, id);
CREATE INDEX IF NOT EXISTS idx_logs_time ON client_logs(created_at);
"""

# 认领字段 / 状态字段迁移（旧库平滑升级）
MIGRATIONS = [
    ("wishes", "claimed_by", "ALTER TABLE wishes ADD COLUMN claimed_by TEXT NOT NULL DEFAULT ''"),
    ("wishes", "claimed_at", "ALTER TABLE wishes ADD COLUMN claimed_at INTEGER NOT NULL DEFAULT 0"),
    ("wishes", "claimed_voter", "ALTER TABLE wishes ADD COLUMN claimed_voter TEXT NOT NULL DEFAULT ''"),
    ("wishes", "status", "ALTER TABLE wishes ADD COLUMN status TEXT NOT NULL DEFAULT 'open'"),
]


_db_lock = threading.RLock()
_conn = None


def db():
    """单连接 + 全局锁：写入频率低，简单可靠。"""
    return _conn


def db_init():
    global _conn
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA synchronous=NORMAL")
    _conn.executescript(SCHEMA)
    _migrate()
    _conn.commit()


def _migrate():
    """补齐新增列，兼容已上线的旧数据库。"""
    for table, column, ddl in MIGRATIONS:
        cols = {r["name"] for r in _conn.execute("PRAGMA table_info(%s)" % table).fetchall()}
        if column not in cols:
            try:
                _conn.execute(ddl)
                log.info("migrate: %s.%s added", table, column)
            except sqlite3.OperationalError as e:
                log.warning("migrate %s.%s failed: %s", table, column, e)


# --------------------------------------------------------------------------
# 文本清洗
# --------------------------------------------------------------------------

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS_RE = re.compile(r"\s+")


def clean_text(raw, limit, allow_newline=False):
    """清洗用户输入：去控制字符、压缩空白、按字符数截断。"""
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raw = str(raw)
    raw = _CTRL_RE.sub("", raw)
    if allow_newline:
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        # 保留换行，其余空白压缩
        parts = [_WS_RE.sub(" ", line).strip() for line in raw.split("\n")]
        raw = "\n".join([p for p in parts if p])
    else:
        raw = _WS_RE.sub(" ", raw).strip()
    # 按「显示宽度」截断，避免 emoji 截半
    out = []
    for ch in raw:
        if len("".join(out)) >= limit:
            break
        if unicodedata.category(ch) in ("Cs", "Co", "Cn"):
            continue
        out.append(ch)
    return "".join(out)[:limit]


def normalize_voter(sn, client_id, ip):
    """稳定化投票者标识：优先设备 SN，其次客户端 id，最后退回 IP。"""
    sn = clean_text(sn, 64)
    client_id = clean_text(client_id, 64)
    if sn:
        return "sn:" + sn
    if client_id:
        return "cid:" + client_id
    return "ip:" + (ip or "0.0.0.0")


# --------------------------------------------------------------------------
# 实时推送（SSE 广播）
# --------------------------------------------------------------------------

class Hub:
    """极简 SSE 广播中心。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._subs = {}          # sub_id -> queue(list)
        self._seq = 0
        self._ver = int(time.time() * 1000)

    def subscribe(self):
        with self._lock:
            self._seq += 1
            sid = self._seq
            self._subs[sid] = []
            return sid

    def unsubscribe(self, sid):
        with self._lock:
            self._subs.pop(sid, None)

    def pending(self, sid):
        with self._lock:
            q = self._subs.get(sid)
            if q is None:
                return None
            out, self._subs[sid] = q, []
            return out

    def publish(self, event, data):
        """广播事件；data 会自动带上服务端版本号。"""
        with self._lock:
            self._ver = int(time.time() * 1000)
            payload = dict(data)
            payload["rev"] = self._ver
            msg = json.dumps(payload, ensure_ascii=False)
            dead = []
            for sid, q in self._subs.items():
                if len(q) >= 200:      # 慢消费者：丢弃积压，防止内存膨胀
                    q.clear()
                q.append((event, msg))
                if len(q) >= 200:
                    dead.append(sid)
            for sid in dead:
                pass
        return msg

    @property
    def clients(self):
        with self._lock:
            return len(self._subs)

    @property
    def rev(self):
        with self._lock:
            return self._ver


hub = Hub()


# --------------------------------------------------------------------------
# 限流
# --------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self._lock = threading.Lock()
        self._buckets = {}       # key -> [timestamps]

    def allow(self, key):
        now = time.time()
        with self._lock:
            arr = self._buckets.get(key)
            if arr is None:
                arr = []
                self._buckets[key] = arr
            cutoff = now - self.window
            # 原地过滤
            arr[:] = [t for t in arr if t >= cutoff]
            if len(arr) >= self.limit:
                return False
            arr.append(now)
            # 轻量清理
            if len(self._buckets) > 20000:
                for k in [k for k, v in self._buckets.items() if not v][:5000]:
                    self._buckets.pop(k, None)
            return True


submit_limiter = RateLimiter(RATE_SUBMIT, RATE_WINDOW_S)
vote_limiter = RateLimiter(RATE_VOTE, RATE_WINDOW_S)
claim_limiter = RateLimiter(RATE_CLAIM, RATE_WINDOW_S)
admin_limiter = RateLimiter(10, 300)


# --------------------------------------------------------------------------
# 业务逻辑
# --------------------------------------------------------------------------

def row_to_wish(r, voted_set=None, with_desc=True, voter=None):
    keys = r.keys()
    d = {
        "id": r["id"],
        "title": r["title"],
        "category": r["category"],
        "nick": r["nick"] or "匿名笔友",
        "votes": r["votes"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }
    if with_desc:
        d["desc"] = r["desc"]
    if voted_set is not None:
        d["voted"] = r["id"] in voted_set

    # 认领信息
    claimed_by = r["claimed_by"] if "claimed_by" in keys else ""
    claimed_at = r["claimed_at"] if "claimed_at" in keys else 0
    claimed_voter = r["claimed_voter"] if "claimed_voter" in keys else ""
    d["claimed"] = bool(claimed_by)
    d["claimed_by"] = claimed_by or ""
    d["claimed_at"] = claimed_at or 0
    d["claim_mine"] = bool(voter and claimed_voter and claimed_voter == voter)

    # 状态
    st = r["status"] if "status" in keys else "open"
    d["status"] = st if st in STATUS_IDS else "open"
    return d


WISH_COLS = ("id,title,desc,category,nick,votes,created_at,updated_at,"
             "claimed_by,claimed_at,claimed_voter,status")


def wish_voted_set(voter):
    if not voter:
        return set()
    with _db_lock:
        rows = db().execute("SELECT wish_id FROM votes WHERE voter=?", (voter,)).fetchall()
    return {r["wish_id"] for r in rows}


def list_wishes(sort="votes", category="", q="", status="", limit=200, offset=0, voter=""):
    where = ["deleted=0"]
    args = []
    if category and category in CATEGORY_IDS:
        where.append("category=?")
        args.append(category)
    if status and status in STATUS_IDS:
        where.append("status=?")
        args.append(status)
    if q:
        where.append("(title LIKE ? OR desc LIKE ?)")
        like = "%" + q + "%"
        args.extend([like, like])

    if sort == "new":
        order = "id DESC"
    elif sort == "votes":
        order = "votes DESC, id DESC"
    else:
        order = "votes DESC, id DESC"

    sql = ("SELECT " + WISH_COLS + " "
           "FROM wishes WHERE " + " AND ".join(where) +
           " ORDER BY " + order + " LIMIT ? OFFSET ?")
    with _db_lock:
        rows = db().execute(sql, args + [limit, offset]).fetchall()
    voted = wish_voted_set(voter)
    return [row_to_wish(r, voted, voter=voter) for r in rows]


def stats():
    with _db_lock:
        c = db()
        total = c.execute("SELECT COUNT(*) n FROM wishes WHERE deleted=0").fetchone()["n"]
        votes = c.execute("SELECT COALESCE(SUM(votes),0) v FROM wishes WHERE deleted=0").fetchone()["v"]
        today0 = int(time.time()) - 86400
        today = c.execute("SELECT COUNT(*) n FROM wishes WHERE deleted=0 AND created_at>=?",
                          (today0,)).fetchone()["n"]
        contributors = c.execute("SELECT COUNT(DISTINCT nick) n FROM wishes WHERE deleted=0 AND nick<>''"
                                 ).fetchone()["n"]
        claimed = c.execute("SELECT COUNT(*) n FROM wishes WHERE deleted=0 AND claimed_by<>''"
                            ).fetchone()["n"]
        doing = c.execute("SELECT COUNT(*) n FROM wishes WHERE deleted=0 AND status='doing'"
                          ).fetchone()["n"]
        done = c.execute("SELECT COUNT(*) n FROM wishes WHERE deleted=0 AND status='done'"
                         ).fetchone()["n"]
        trashed = c.execute("SELECT COUNT(*) n FROM wishes WHERE deleted=1").fetchone()["n"]
    return {"wishes": total, "votes": votes, "today": today,
            "contributors": contributors, "claimed": claimed,
            "doing": doing, "done": done, "trashed": trashed}


def create_wish(title, desc, category, nick, sn):
    now = int(time.time())
    with _db_lock:
        c = db()
        cur = c.execute(
            "INSERT INTO wishes(title,desc,category,nick,sn,votes,created_at,updated_at,deleted)"
            " VALUES(?,?,?,?,?,0,?,?,0)",
            (title, desc, category, nick, sn, now, now))
        c.commit()
        wid = cur.lastrowid
        r = c.execute("SELECT " + WISH_COLS + " FROM wishes WHERE id=?", (wid,)).fetchone()
    return row_to_wish(r)


def vote(wish_id, voter, delta=1):
    """返回 (status, wish_dict, my_votes)。status: 'added' | 'removed' | 'notfound'"""
    now = int(time.time())
    with _db_lock:
        c = db()
        r = c.execute("SELECT id FROM wishes WHERE id=? AND deleted=0", (wish_id,)).fetchone()
        if r is None:
            return "notfound", None, 0
        exists = c.execute("SELECT 1 FROM votes WHERE wish_id=? AND voter=?",
                           (wish_id, voter)).fetchone()
        if exists:
            if delta < 0:
                c.execute("DELETE FROM votes WHERE wish_id=? AND voter=?", (wish_id, voter))
                c.execute("UPDATE wishes SET votes=MAX(0,votes-1), updated_at=? WHERE id=?",
                          (now, wish_id))
                status = "removed"
            else:
                status = "added"   # 重复 +1：幂等，不再累加
        else:
            c.execute("INSERT INTO votes(wish_id,voter,created_at) VALUES(?,?,?)",
                      (wish_id, voter, now))
            c.execute("UPDATE wishes SET votes=votes+1, updated_at=? WHERE id=?",
                      (now, wish_id))
            status = "added"
        c.commit()
        r = c.execute("SELECT " + WISH_COLS + " FROM wishes WHERE id=?", (wish_id,)).fetchone()
        mine = c.execute("SELECT COUNT(*) n FROM votes WHERE wish_id=? AND voter=?",
                         (wish_id, voter)).fetchone()["n"]
    return status, row_to_wish(r, {wish_id} if mine else set(), voter=voter), mine


# --------------------------------------------------------------------------
# 认领
# --------------------------------------------------------------------------

CLAIM_ERR_TAKEN = "taken"
CLAIM_ERR_NOTFOUND = "notfound"
CLAIM_ERR_NOTOWNER = "notowner"


def claim_wish(wish_id, nick, voter, sn=""):
    """认领愿望。

    规则：
      - 一个愿望同时只能有一个有效认领；
      - 重复认领（本人）幂等，可更新昵称；
      - 昵称由服务端落库（wishes.claimed_by）并写 claims 审计日志。

    返回 (status, wish_dict, info)
      status: 'claimed' | 'reclaimed' | 'taken' | 'notfound' | 'nick'
    """
    nick = clean_text(nick, MAX_NICK)
    if nick is None:
        nick = ""
    if not nick:
        return "nick", None, {"message": "请填写昵称后再认领"}

    now = int(time.time())
    with _db_lock:
        c = db()
        r = c.execute("SELECT id, claimed_by, claimed_voter FROM wishes WHERE id=? AND deleted=0",
                      (wish_id,)).fetchone()
        if r is None:
            return "notfound", None, {}
        cur_by = r["claimed_by"] or ""
        cur_voter = r["claimed_voter"] or ""

        if cur_by and cur_voter and cur_voter != voter:
            return "taken", None, {"claimed_by": cur_by, "claimed_at": 0}

        updated = bool(cur_by) and cur_voter == voter
        if updated:
            c.execute("UPDATE wishes SET claimed_by=?, claimed_voter=?, claimed_at=?, updated_at=? "
                      "WHERE id=?", (nick, voter, now, now, wish_id))
        else:
            c.execute("UPDATE wishes SET claimed_by=?, claimed_voter=?, claimed_at=?, updated_at=? "
                      "WHERE id=?", (nick, voter, now, now, wish_id))

        # 审计日志：同一次认领只保留一条有效记录
        prev = c.execute("SELECT id FROM claims WHERE wish_id=? AND voter=? AND released_at=0",
                         (wish_id, voter)).fetchone()
        if prev:
            c.execute("UPDATE claims SET nick=?, created_at=? WHERE id=?",
                      (nick, now, prev["id"]))
        else:
            c.execute("INSERT INTO claims(wish_id,nick,voter,sn,created_at,released_at) "
                      "VALUES(?,?,?,?,?,0)", (wish_id, nick, voter, sn or "", now))
        c.commit()
        row = c.execute("SELECT " + WISH_COLS + " FROM wishes WHERE id=?", (wish_id,)).fetchone()

    w = row_to_wish(row, voter=voter)
    return ("reclaimed" if updated else "claimed"), w, {"nick": nick}


def release_wish(wish_id, voter):
    """释放认领：只有认领人本人或管理员可释放。"""
    now = int(time.time())
    with _db_lock:
        c = db()
        r = c.execute("SELECT id, claimed_by, claimed_voter FROM wishes WHERE id=? AND deleted=0",
                      (wish_id,)).fetchone()
        if r is None:
            return "notfound", None
        if not r["claimed_by"]:
            return "notclaimed", None
        if r["claimed_voter"] != voter:
            return "notowner", None
        c.execute("UPDATE wishes SET claimed_by='', claimed_voter='', claimed_at=0, updated_at=? "
                  "WHERE id=?", (now, wish_id))
        c.execute("UPDATE claims SET released_at=? WHERE wish_id=? AND voter=? AND released_at=0",
                  (now, wish_id, voter))
        c.commit()
        row = c.execute("SELECT " + WISH_COLS + " FROM wishes WHERE id=?", (wish_id,)).fetchone()
    return "released", row_to_wish(row, voter=voter)


def set_status(wish_id, status):
    """调整愿望状态。返回 (status, wish_dict)"""
    if status not in STATUS_IDS:
        return "badstatus", None
    now = int(time.time())
    with _db_lock:
        c = db()
        r = c.execute("SELECT id FROM wishes WHERE id=? AND deleted=0", (wish_id,)).fetchone()
        if r is None:
            return "notfound", None
        c.execute("UPDATE wishes SET status=?, updated_at=? WHERE id=?", (status, now, wish_id))
        c.commit()
        row = c.execute("SELECT " + WISH_COLS + " FROM wishes WHERE id=?", (wish_id,)).fetchone()
    return "ok", row_to_wish(row)


def delete_wish(wish_id, hard=False):
    """删除愿望。hard=True 时物理删除（含投票与认领记录）。"""
    now = int(time.time())
    with _db_lock:
        c = db()
        r = c.execute("SELECT id FROM wishes WHERE id=?", (wish_id,)).fetchone()
        if r is None:
            return "notfound", None
        if hard:
            c.execute("DELETE FROM votes WHERE wish_id=?", (wish_id,))
            c.execute("DELETE FROM claims WHERE wish_id=?", (wish_id,))
            c.execute("DELETE FROM wishes WHERE id=?", (wish_id,))
        else:
            c.execute("UPDATE wishes SET deleted=1, updated_at=? WHERE id=?", (now, wish_id))
        c.commit()
    return ("deleted" if hard else "trashed"), None


def restore_wish(wish_id):
    now = int(time.time())
    with _db_lock:
        c = db()
        r = c.execute("SELECT id FROM wishes WHERE id=?", (wish_id,)).fetchone()
        if r is None:
            return "notfound", None
        c.execute("UPDATE wishes SET deleted=0, updated_at=? WHERE id=?", (now, wish_id))
        c.commit()
        row = c.execute("SELECT " + WISH_COLS + " FROM wishes WHERE id=?", (wish_id,)).fetchone()
    return "ok", row_to_wish(row)


# --------------------------------------------------------------------------
# 应用更新（发布信息存 meta 表，键名 release）
# --------------------------------------------------------------------------

RELEASE_KEY = "release"


def ver_tuple(v):
    """'1.2.10' -> (1,2,10)；非数字段截断。"""
    out = []
    for part in str(v or "").split(".")[:3]:
        n = 0
        for ch in part:
            if ch.isdigit():
                n = n * 10 + (ord(ch) - 48)
            else:
                break
        out.append(n)
    while len(out) < 3:
        out.append(0)
    return tuple(out)


def version_gt(a, b):
    """a 比 b 新 -> True（按数字段比较，避免字符串比较的 1.2.9 > 1.2.10 陷阱）"""
    if not a:
        return False
    if not b:
        return True
    return ver_tuple(a) > ver_tuple(b)


def get_release():
    with _db_lock:
        row = db().execute("SELECT v FROM meta WHERE k=?", (RELEASE_KEY,)).fetchone()
    if not row:
        return None
    try:
        v = json.loads(row["v"])
        return v if isinstance(v, dict) else None
    except (ValueError, TypeError):
        return None


def save_release(payload):
    with _db_lock:
        db().execute(
            "INSERT INTO meta(k,v) VALUES(?,?) "
            "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (RELEASE_KEY, json.dumps(payload, ensure_ascii=False)))
        db().commit()
    return payload


def clear_release():
    with _db_lock:
        db().execute("DELETE FROM meta WHERE k=?", (RELEASE_KEY,))
        db().commit()


def pkg_path(name):
    """包名安全校验 + 返回绝对路径。"""
    name = str(name or "").strip()
    if not name or "/" in name or "\\" in name or ".." in name or name.startswith("."):
        return None
    p = os.path.join(PKG_DIR, name)
    return p if os.path.isfile(p) else None


def pkg_info(name):
    p = pkg_path(name)
    if not p:
        return None
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(256 * 1024), b""):
            h.update(chunk)
    return {"name": name, "size": os.path.getsize(p), "md5": h.hexdigest()}


def build_release(params, base_url):
    """由面板参数组装发布信息（自动补 size/md5/url）。"""
    version = clean_text(params.get("version"), 32)
    file_name = clean_text(params.get("file"), 128)
    notes = clean_text(params.get("notes"), 1000, allow_newline=True)
    platform = clean_text(params.get("platform"), 16) or "rk"
    force = 1 if str(params.get("force", "0")) in ("1", "true", "yes") else 0

    if not version:
        return None, "缺少版本号"
    if not file_name:
        return None, "缺少安装包文件名"
    info = pkg_info(file_name)
    if not info:
        return None, "安装包不存在: " + file_name

    payload = {
        "version": version,
        "platform": platform,
        "file": file_name,
        "url": base_url.rstrip("/") + "/pkg/" + file_name,
        "size": info["size"],
        "md5": info["md5"],
        "notes": notes,
        "force": force,
        "updated_at": int(time.time()),
    }
    return payload, None


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "WishPool/1.0"
    protocol_version = "HTTP/1.1"

    # ---- 基础工具 ----
    def log_message(self, fmt, *args):
        # 去掉查询串再记日志，避免管理密码等敏感参数落盘
        try:
            msg = fmt % args
        except (TypeError, ValueError):
            msg = str(fmt)
        msg = re.sub(r"\?\S*", "", msg)
        log.info("%s - %s", self.client_address[0], msg)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-Admin-Pass,X-Client-Id")
        self.send_header("Access-Control-Max-Age", "86400")

    def send_json(self, obj, code=200):
        body = json_bytes(obj)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_file(self, path, ctype, download_name=None):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            self.send_error(404, "Not Found")
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if download_name:
            ascii_name = download_name.encode("ascii", "ignore").decode() or "download.bin"
            self.send_header(
                "Content-Disposition",
                "attachment; filename=\"%s\"; filename*=UTF-8''%s"
                % (ascii_name, quote(download_name, safe="")),
            )
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Accept-Ranges", "none")
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def serve_pkg(self, name):
        """下载 PKG_DIR 下的安装包。"""
        from urllib.parse import unquote
        name = unquote(name or "")

        # 目录列表
        if name in ("", "/"):
            files = []
            try:
                for fn in sorted(os.listdir(PKG_DIR)):
                    fp = os.path.join(PKG_DIR, fn)
                    if os.path.isfile(fp):
                        files.append({"name": fn, "size": os.path.getsize(fp),
                                      "url": "/pkg/" + quote(fn, safe="")})
            except OSError:
                pass
            self.send_json({"ok": True, "files": files})
            return

        # 防目录穿越
        if "/" in name or "\\" in name or ".." in name or name.startswith("."):
            self.send_json({"ok": False, "error": "bad name"}, 400)
            return

        fp = os.path.join(PKG_DIR, name)
        if not os.path.isfile(fp):
            self.send_json({"ok": False, "error": "not found"}, 404)
            return

        ctype = "application/octet-stream"
        if name.endswith(".amr"):
            ctype = "application/vnd.youdao.amr"
        self.send_file(fp, ctype, download_name=name)

    def read_body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            return b""
        if n > MAX_BODY:
            raise ValueError("body too large")
        return self.rfile.read(n)

    def read_json(self):
        raw = self.read_body()
        if not raw:
            return {}
        try:
            v = json.loads(raw.decode("utf-8"))
        except Exception:
            raise ValueError("invalid json")
        if not isinstance(v, dict):
            raise ValueError("expect object")
        return v

    def client_ip(self):
        # 信任反向代理头（若直连则就是真实 IP）
        xff = self.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        real = self.headers.get("X-Real-IP")
        if real:
            return real.strip()
        return self.client_address[0]

    def voter_key(self, params=None, payload=None):
        return normalize_voter(
            (payload or {}).get("sn") or (params or {}).get("sn"),
            (payload or {}).get("client_id") or (params or {}).get("client_id")
            or self.headers.get("X-Client-Id"),
            self.client_ip(),
        )

    def admin_ok(self):
        supplied = self.headers.get("X-Admin-Pass") or ""
        if not supplied:
            return False
        return hmac.compare_digest(supplied, ADMIN_PASS)

    def admin_ok_with(self, supplied):
        if not supplied:
            return False
        return hmac.compare_digest(str(supplied), ADMIN_PASS)

    def public_base(self):
        """推断对外访问地址（优先代理头，其次 Host）。"""
        proto = (self.headers.get("X-Forwarded-Proto") or "http").split(",")[0].strip()
        host = (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "").split(",")[0].strip()
        if not host:
            host = "%s:%d" % (HOST if HOST != "0.0.0.0" else "127.0.0.1", PORT)
        return proto + "://" + host

    def claim_authorized(self, payload=None):
        """认领/释放需要管理密码：优先取请求头，其次取参数。"""
        if self.admin_ok():
            return True
        p = (payload or {}).get("pass") or (payload or {}).get("admin_pass")
        return self.admin_ok_with(p)

    # ---- 路由 ----
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path.rstrip("/") or "/"
        qs = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}

        if p in ("/", "/index.html", "/panel"):
            self.send_file(PANEL_PATH, "text/html; charset=utf-8")
            return

        if p == "/pkg":
            self.serve_pkg("")
            return
        if p.startswith("/pkg/"):
            self.serve_pkg(p[len("/pkg/"):])
            return

        if p == "/healthz":
            self.send_json({"ok": True, "rev": hub.rev, "clients": hub.clients})
            return

        if p == "/api/meta":
            self.send_json({
                "ok": True,
                "categories": CATEGORIES,
                "statuses": STATUSES,
                "server_time": int(time.time()),
                "rev": hub.rev,
                "max_title": MAX_TITLE,
                "max_desc": MAX_DESC,
                "max_nick": MAX_NICK,
            })
            return

        if p == "/api/wishes":
            try:
                limit = max(1, min(500, int(qs.get("limit", "200"))))
                offset = max(0, int(qs.get("offset", "0")))
            except ValueError:
                limit, offset = 200, 0
            items = list_wishes(
                sort=qs.get("sort", "votes"),
                category=qs.get("category", ""),
                q=clean_text(qs.get("q", ""), 40),
                status=qs.get("status", ""),
                limit=limit, offset=offset,
                voter=self.voter_key(params=qs),
            )
            self.send_json({
                "ok": True,
                "items": items,
                "sort": qs.get("sort", "votes"),
                "stats": stats(),
                "rev": hub.rev,
            })
            return

        if p == "/api/stats":
            _s = stats()
            _s["ok"] = True
            self.send_json(_s)
            return

        if p == "/app-update":
            rel = get_release()
            cur = clean_text(qs.get("version", ""), 32)
            plat = clean_text(qs.get("platform", ""), 16)
            if not rel:
                self.send_json({"ok": True, "hasUpdate": False, "reason": "no-release"})
                return
            if plat and rel.get("platform") not in ("", "all", plat):
                self.send_json({"ok": True, "hasUpdate": False, "reason": "platform"})
                return
            newer = version_gt(rel.get("version", ""), cur)
            self.send_json({
                "ok": True,
                "hasUpdate": bool(newer),
                "force": int(rel.get("force", 0)) if newer else 0,
                "latest": {
                    "version": rel.get("version", ""),
                    "url": rel.get("url", ""),
                    "size": rel.get("size", 0),
                    "md5": rel.get("md5", ""),
                    "notes": rel.get("notes", ""),
                    "platform": rel.get("platform", ""),
                },
                "current": cur,
            })
            return

        if p == "/api/admin/pkg":
            files = []
            try:
                for fn in sorted(os.listdir(PKG_DIR)):
                    fp = os.path.join(PKG_DIR, fn)
                    if os.path.isfile(fp):
                        files.append({"name": fn, "size": os.path.getsize(fp)})
            except OSError:
                pass
            self.send_json({"ok": True, "files": files, "release": get_release()})
            return

        # ---- 写操作的 GET 形式 ----
        # 词典笔真机上原生 http 的 POST body 不可靠（会发空 body），
        # 因此笔端统一走 GET + query；面板仍用 POST。
        try:
            if p == "/api/wish/add":
                self.api_create_wish(payload=qs)
                return
            m = re.match(r"^/api/wish/(\d+)/vote$", p)
            if m:
                self.api_vote(int(m.group(1)), qs)
                return
            m = re.match(r"^/api/wish/(\d+)/unvote$", p)
            if m:
                self.api_vote(int(m.group(1)), qs, force_delta=-1)
                return
            m = re.match(r"^/api/wish/(\d+)/claim$", p)
            if m:
                self.api_claim(int(m.group(1)), qs, payload=qs)
                return
            m = re.match(r"^/api/wish/(\d+)/release$", p)
            if m:
                self.api_release(int(m.group(1)), qs, payload=qs)
                return
            if p == "/api/log":
                self.api_log(payload=qs)
                return
        except ValueError as e:
            self.send_json({"ok": False, "error": str(e)}, 400)
            return
        except Exception:      # noqa: BLE001
            log.exception("GET write %s failed", p)
            self.send_json({"ok": False, "error": "internal error"}, 500)
            return

        if p == "/api/stream":
            self.stream_sse(qs)
            return

        if p.startswith("/api/admin/"):
            self.admin_get(p[len("/api/admin/"):], qs)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        u = urlparse(self.path)
        p = u.path.rstrip("/") or "/"
        qs = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}

        try:
            if p == "/api/wish":
                self.api_create_wish()
                return
            m = re.match(r"^/api/wish/(\d+)/vote$", p)
            if m:
                self.api_vote(int(m.group(1)), qs)
                return
            m = re.match(r"^/api/wish/(\d+)/unvote$", p)
            if m:
                self.api_vote(int(m.group(1)), qs, force_delta=-1)
                return
            m = re.match(r"^/api/wish/(\d+)/claim$", p)
            if m:
                self.api_claim(int(m.group(1)), qs)
                return
            m = re.match(r"^/api/wish/(\d+)/release$", p)
            if m:
                self.api_release(int(m.group(1)), qs)
                return
            if p == "/api/log":
                self.api_log()
                return
            if p.startswith("/api/admin/"):
                self.admin_post(p[len("/api/admin/"):], qs)
                return
        except ValueError as e:
            self.send_json({"ok": False, "error": str(e)}, 400)
            return
        except Exception as e:      # noqa: BLE001
            log.exception("POST %s failed", p)
            self.send_json({"ok": False, "error": "internal error"}, 500)
            return

        self.send_error(404, "Not Found")

    def do_PUT(self):
        """安装包上传：PUT /api/admin/pkg/upload?name=xxx.amr（裸二进制）"""
        u = urlparse(self.path)
        p = u.path.rstrip("/") or "/"
        qs = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}

        if p != "/api/admin/pkg/upload":
            self.send_error(404, "Not Found")
            return
        if not self.admin_ok():
            self.send_json({"ok": False, "error": "unauthorized"}, 401)
            return

        name = clean_text(qs.get("name", ""), 128)
        if not name or "/" in name or "\\" in name or ".." in name or name.startswith("."):
            self.send_json({"ok": False, "error": "非法文件名"}, 400)
            return
        if not name.endswith(".amr"):
            self.send_json({"ok": False, "error": "只接受 .amr"}, 400)
            return

        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            self.send_json({"ok": False, "error": "空文件"}, 400)
            return
        if n > MAX_PKG:
            self.send_json({"ok": False, "error": "文件过大"}, 413)
            return

        os.makedirs(PKG_DIR, exist_ok=True)
        tmp = os.path.join(PKG_DIR, name + ".part")
        dst = os.path.join(PKG_DIR, name)
        got = 0
        h = hashlib.md5()
        try:
            with open(tmp, "wb") as f:
                while got < n:
                    chunk = self.rfile.read(min(256 * 1024, n - got))
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
            if got != n:
                os.unlink(tmp)
                self.send_json({"ok": False, "error": "上传不完整"}, 400)
                return
            os.replace(tmp, dst)
        except OSError as e:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            log.exception("pkg upload failed")
            self.send_json({"ok": False, "error": "写入失败: %s" % e}, 500)
            return

        log.info("pkg uploaded: %s (%d bytes)", name, got)
        self.send_json({"ok": True, "name": name, "size": got, "md5": h.hexdigest()})

    def do_DELETE(self):
        u = urlparse(self.path)
        p = u.path.rstrip("/") or "/"
        qs = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}
        m = re.match(r"^/api/admin/wish/(\d+)$", p)
        if m:
            if not self.admin_ok():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            wid = int(m.group(1))
            hard = qs.get("hard") in ("1", "true", "yes")
            status, _ = delete_wish(wid, hard=hard)
            if status == "notfound":
                self.send_json({"ok": False, "error": "愿望不存在"}, 404)
                return
            hub.publish("wish_deleted", {"id": wid, "hard": hard})
            self.send_json({"ok": True, "status": status})
            return
        self.send_error(404, "Not Found")

    # ---- 业务接口 ----
    def api_create_wish(self, payload=None):
        if payload is None:
            payload = self.read_json()
        if not submit_limiter.allow(self.client_ip()):
            self.send_json({"ok": False, "error": "提交太频繁，请稍后再试"}, 429)
            return

        title = clean_text(payload.get("title"), MAX_TITLE)
        desc = clean_text(payload.get("desc"), MAX_DESC, allow_newline=True)
        category = clean_text(payload.get("category"), 16)
        nick = clean_text(payload.get("nick"), MAX_NICK) or "匿名笔友"
        sn = clean_text(payload.get("sn"), 64)

        if len(title) < 2:
            self.send_json({"ok": False, "error": "标题至少 2 个字"}, 400)
            return
        if category not in CATEGORY_IDS:
            category = "other"

        w = create_wish(title, desc, category, nick, sn)
        # 创建者自动视为已支持
        voter = self.voter_key(payload=payload)
        vote(w["id"], voter, 1)
        with _db_lock:
            r = db().execute("SELECT " + WISH_COLS + " FROM wishes WHERE id=?",
                             (w["id"],)).fetchone()
        w = row_to_wish(r, {w["id"]}, voter=voter)
        hub.publish("wish_added", {"wish": w})
        self.send_json({"ok": True, "wish": w, "stats": stats()})

    def api_vote(self, wid, qs, force_delta=1):
        if not vote_limiter.allow(self.client_ip()):
            self.send_json({"ok": False, "error": "+1 太频繁"}, 429)
            return
        voter = self.voter_key(params=qs)
        status, w, mine = vote(wid, voter, force_delta)
        if status == "notfound":
            self.send_json({"ok": False, "error": "愿望不存在"}, 404)
            return
        hub.publish("wish_voted", {"wish": {"id": w["id"], "votes": w["votes"]},
                                   "status": status})
        self.send_json({"ok": True, "status": status, "wish": w, "my_votes": mine,
                        "stats": stats()})

    def api_claim(self, wid, qs, payload=None):
        """认领愿望：服务端记录认领人昵称并写审计日志。"""
        if payload is None:
            try:
                payload = self.read_json()
            except ValueError:
                payload = {}
        if not claim_limiter.allow(self.client_ip()):
            self.send_json({"ok": False, "error": "操作太频繁"}, 429)
            return

        if not self.claim_authorized(payload):
            self.send_json({
                "ok": False,
                "error": "认领需要管理密码",
                "need_pass": True,
            }, 401)
            return

        nick = clean_text(payload.get("nick") or qs.get("nick"), MAX_NICK)
        sn = clean_text(payload.get("sn") or qs.get("sn"), 64)
        voter = self.voter_key(qs, payload)

        status, w, info = claim_wish(wid, nick, voter, sn)
        if status == "notfound":
            self.send_json({"ok": False, "error": "愿望不存在"}, 404)
            return
        if status == "nick":
            self.send_json({"ok": False, "error": "请填写昵称后再认领"}, 400)
            return
        if status == "taken":
            self.send_json({
                "ok": False,
                "error": "已被「%s」认领" % info.get("claimed_by", ""),
                "claimed_by": info.get("claimed_by", ""),
            }, 409)
            return

        hub.publish("wish_claimed", {
            "wish": {"id": w["id"], "claimed_by": w["claimed_by"], "votes": w["votes"]},
            "action": status,
        })
        self.send_json({"ok": True, "status": status, "wish": w, "stats": stats()})

    def api_release(self, wid, qs, payload=None):
        """释放认领（需管理密码）。"""
        if payload is None:
            try:
                payload = self.read_json()
            except ValueError:
                payload = {}
        if not self.claim_authorized(payload):
            self.send_json({
                "ok": False,
                "error": "释放认领需要管理密码",
                "need_pass": True,
            }, 401)
            return
        voter = self.voter_key(qs, payload)
        status, w = release_wish(wid, voter)
        if status == "notfound":
            self.send_json({"ok": False, "error": "愿望不存在"}, 404)
            return
        if status == "notclaimed":
            self.send_json({"ok": False, "error": "该愿望还没被认领"}, 400)
            return
        if status == "notowner":
            self.send_json({"ok": False, "error": "只有认领人可以释放"}, 403)
            return
        hub.publish("wish_released", {"wish": {"id": w["id"]}, "action": "released"})
        self.send_json({"ok": True, "status": status, "wish": w, "stats": stats()})

    def api_log(self, payload=None):
        """笔端日志上报。body: {sn, client_id, version, lines:[{t,l,m}] 或 "t|l|m\n..."}"""
        if payload is None:
            try:
                payload = self.read_json()
            except ValueError:
                payload = {}
        sn = clean_text(payload.get("sn"), 64)
        cid = clean_text(payload.get("client_id"), 64)
        ver = clean_text(payload.get("version"), 32)

        lines = payload.get("lines")
        if isinstance(lines, str):
            parsed = []
            for ln in lines.split("\n"):
                ln = ln.strip()
                if not ln:
                    continue
                parts = ln.split("|", 2)
                if len(parts) == 3:
                    try:
                        parsed.append({"t": int(parts[0]), "l": parts[1], "m": parts[2]})
                        continue
                    except ValueError:
                        pass
                parsed.append({"t": int(time.time()), "l": "info", "m": ln})
            lines = parsed[-200:]
        if not isinstance(lines, list):
            lines = []

        now = int(time.time())
        rows = []
        for item in lines[-200:]:
            if isinstance(item, dict):
                m = clean_text(item.get("m"), 500)
                lv = clean_text(item.get("l"), 8) or "info"
                t = item.get("t")
                try:
                    t = int(t)
                except (TypeError, ValueError):
                    t = now
            else:
                m = clean_text(item, 500)
                lv = "info"
                t = now
            if m:
                rows.append((sn, cid, ver, lv, m, t))

        if rows:
            with _db_lock:
                db().executemany(
                    "INSERT INTO client_logs(sn,client_id,version,level,msg,created_at) "
                    "VALUES(?,?,?,?,?,?)", rows)
                db().commit()
            # 只保留最近 20000 条
            with _db_lock:
                db().execute("DELETE FROM client_logs WHERE id < "
                             "(SELECT MAX(id)-20000 FROM client_logs)")
                db().commit()

        log.info("client log from sn=%s ver=%s lines=%d", sn or "-", ver or "-", len(rows))
        self.send_json({"ok": True, "received": len(rows)})

    # ---- 管理接口 ----
    def admin_get(self, sub, qs):
        if sub == "ping":
            self.send_json({"ok": True, "authed": self.admin_ok()})
            return
        if not self.admin_ok():
            self.send_json({"ok": False, "error": "unauthorized"}, 401)
            return
        if sub == "wishes":
            only_deleted = qs.get("deleted") in ("1", "true")
            with _db_lock:
                if only_deleted:
                    rows = db().execute(
                        "SELECT id,title,desc,category,nick,votes,created_at,deleted,status,"
                        "claimed_by,claimed_at,claimed_voter FROM wishes "
                        "WHERE deleted=1 ORDER BY id DESC LIMIT 2000").fetchall()
                else:
                    rows = db().execute(
                        "SELECT id,title,desc,category,nick,votes,created_at,deleted,status,"
                        "claimed_by,claimed_at,claimed_voter FROM wishes "
                        "WHERE deleted=0 ORDER BY id DESC LIMIT 2000").fetchall()
            self.send_json({"ok": True, "items": [dict(r) for r in rows],
                            "stats": stats(), "statuses": STATUSES})
            return
        if sub == "claims":
            with _db_lock:
                rows = db().execute(
                    "SELECT c.id, c.wish_id, c.nick, c.voter, c.sn, c.created_at, c.released_at,"
                    " w.title FROM claims c LEFT JOIN wishes w ON w.id=c.wish_id "
                    "ORDER BY c.id DESC LIMIT 1000").fetchall()
            self.send_json({"ok": True, "items": [dict(r) for r in rows]})
            return
        if sub == "logs":
            sn = clean_text(qs.get("sn", ""), 64)
            try:
                limit = max(1, min(3000, int(qs.get("limit", "500"))))
            except ValueError:
                limit = 500
            with _db_lock:
                if sn:
                    rows = db().execute(
                        "SELECT id,sn,client_id,version,level,msg,created_at FROM client_logs "
                        "WHERE sn=? ORDER BY id DESC LIMIT ?", (sn, limit)).fetchall()
                else:
                    rows = db().execute(
                        "SELECT id,sn,client_id,version,level,msg,created_at FROM client_logs "
                        "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            self.send_json({"ok": True, "items": [dict(r) for r in rows]})
            return
        if sub == "logs/devices":
            with _db_lock:
                rows = db().execute(
                    "SELECT sn, version, MAX(created_at) last_at, COUNT(*) n "
                    "FROM client_logs GROUP BY sn ORDER BY last_at DESC LIMIT 200").fetchall()
            self.send_json({"ok": True, "items": [dict(r) for r in rows]})
            return
        self.send_json({"ok": False, "error": "unknown"}, 404)

    def admin_post(self, sub, qs):
        if sub == "ping":
            self.send_json({"ok": True, "authed": self.admin_ok()})
            return
        if not admin_limiter.allow(self.client_ip()):
            self.send_json({"ok": False, "error": "too many attempts"}, 429)
            return
        if not self.admin_ok():
            self.send_json({"ok": False, "error": "unauthorized"}, 401)
            return
        if sub == "seed":
            # 由服务端种子数据一键灌入演示愿望
            created = seed_demo()
            self.send_json({"ok": True, "created": created, "stats": stats()})
            return
        if sub == "restore":
            wid = int(qs.get("id", "0"))
            st, w = restore_wish(wid)
            if st == "notfound":
                self.send_json({"ok": False, "error": "愿望不存在"}, 404)
                return
            hub.publish("wish_restored", {"wish": {"id": wid}})
            self.send_json({"ok": True, "wish": w})
            return
        if sub == "status":
            wid = int(qs.get("id", "0"))
            target = qs.get("status", "")
            st, w = set_status(wid, target)
            if st == "notfound":
                self.send_json({"ok": False, "error": "愿望不存在"}, 404)
                return
            if st == "badstatus":
                self.send_json({"ok": False, "error": "无效状态", "statuses": STATUSES}, 400)
                return
            hub.publish("wish_status", {"wish": {"id": wid, "status": w["status"]}})
            self.send_json({"ok": True, "wish": w, "stats": stats()})
            return
        if sub == "purge":
            # 清空所有已软删除的愿望（物理删除）
            with _db_lock:
                rows = db().execute("SELECT id FROM wishes WHERE deleted=1").fetchall()
                n = len(rows)
                for r in rows:
                    db().execute("DELETE FROM votes WHERE wish_id=?", (r["id"],))
                    db().execute("DELETE FROM claims WHERE wish_id=?", (r["id"],))
                db().execute("DELETE FROM wishes WHERE deleted=1")
                db().commit()
            hub.publish("snapshot", {})
            self.send_json({"ok": True, "purged": n})
            return
        if sub == "release/save":
            base = self.public_base()
            payload, err = build_release(qs, base)
            if err:
                self.send_json({"ok": False, "error": err}, 400)
                return
            save_release(payload)
            log.info("release saved: v%s %s", payload["version"], payload["file"])
            self.send_json({"ok": True, "release": payload})
            return
        if sub == "release/clear":
            clear_release()
            self.send_json({"ok": True})
            return
        self.send_json({"ok": False, "error": "unknown"}, 404)

    # ---- SSE ----
    def stream_sse(self, qs):
        sid = hub.subscribe()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self._cors()
        self.end_headers()
        self.close_connection = True
        try:
            # 首帧：立即同步一次全量，保证新客户端一次到位
            payload = json_bytes({
                "items": list_wishes(sort=qs.get("sort", "votes"),
                                     voter=self.voter_key(params=qs)),
                "stats": stats(),
                "rev": hub.rev,
            }).decode("utf-8")
            self._sse_write("snapshot", payload)
            last_ping = time.time()
            while True:
                q = hub.pending(sid)
                if q is None:
                    break
                if q:
                    for ev, data in q:
                        self._sse_write(ev, data)
                else:
                    if time.time() - last_ping > 15:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                        last_ping = time.time()
                    time.sleep(0.35)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            hub.unsubscribe(sid)

    def _sse_write(self, event, data_json):
        msg = ("event: %s\ndata: %s\n\n" % (event, data_json)).encode("utf-8")
        self.wfile.write(msg)
        self.wfile.flush()


# --------------------------------------------------------------------------
# 演示种子数据（部署后可选，仅用于让面板一上手就有内容）
# --------------------------------------------------------------------------

DEMO = [
    ("笔上哔哩下载收藏", "希望能把收藏夹和追番列表做出来，离线缓存也想要", "app", "洛"),
    ("TXT 阅读器支持标记", "边读边做标记，下次打开能回到上次位置", "read", "阿澄"),
    ("笔画练字打分", "写完一个字后给个评分，像作业批改那样", "read", "小满"),
    ("单词本导出", "查过的词能一键导出成 CSV", "feat", "Ocean"),
    ("笔上我的世界", "方块沙盒，能联机更好", "game", "Steven"),
    ("桌面小组件", "待机页显示今日单词和天气", "system", "灯灯"),
    ("局域网文件快传", "两台笔之间互传图片和文本", "feat", "大冲"),
    ("错题本", "拍照识别错题自动归档", "read", "清和"),
    ("五子棋人机对战", "带难度选择，能悔棋", "game", "棋圣"),
    ("锁屏倒计时", "自习时锁屏显示剩余时间", "system", "自习人"),
]


def seed_demo():
    now = int(time.time())
    created = 0
    with _db_lock:
        c = db()
        n = c.execute("SELECT COUNT(*) n FROM wishes").fetchone()["n"]
        if n > 0:
            return 0
        for i, (title, desc, cat, nick) in enumerate(DEMO):
            votes = max(0, 41 - i * 4 - (i % 3))
            c.execute(
                "INSERT INTO wishes(title,desc,category,nick,sn,votes,created_at,updated_at,deleted)"
                " VALUES(?,?,?,?,?,?,?,?,0)",
                (title, desc, cat, nick, "", votes, now - 3600 * (i + 1), now - 3600 * (i + 1)))
            created += 1
        c.commit()
    if created:
        try:
            hub.publish("snapshot", {"items": list_wishes(), "stats": stats()})
        except Exception:
            pass
    return created


# --------------------------------------------------------------------------
# 管理密码
# --------------------------------------------------------------------------

def _load_admin_pass():
    env = os.environ.get("ADMIN_PASS")
    if env:
        return env
    path = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "admin_pass.txt")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                v = f.read().strip()
            if v:
                return v
        except OSError:
            pass
    v = secrets.token_urlsafe(12)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(v + "\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except OSError:
        pass
    return v


ADMIN_PASS = None


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    global ADMIN_PASS
    _setup_logging()
    ADMIN_PASS = _load_admin_pass()
    db_init()

    ports = PORTS

    servers = []
    for p in ports:
        try:
            srv = ThreadingHTTPServer((HOST, p), Handler)
            srv.daemon_threads = True
            servers.append((p, srv))
        except OSError as e:
            log.error("绑定端口 %d 失败: %s", p, e)

    if not servers:
        log.error("没有可用端口，退出")
        return

    log.info("许愿池服务已启动，监听: %s (db=%s)",
             ", ".join("http://%s:%d" % (HOST, p) for p, _ in servers), DB_PATH)
    for p, _ in servers:
        log.info("  大屏面板: http://<服务器IP>:%d/", p)

    threads = []
    for p, srv in servers[1:]:
        t = threading.Thread(target=srv.serve_forever, name="http-%d" % p, daemon=True)
        t.start()
        threads.append(t)

    try:
        servers[0][1].serve_forever()
    except KeyboardInterrupt:
        log.info("shutdown")
    finally:
        for _, srv in servers:
            try:
                srv.server_close()
            except OSError:
                pass


if __name__ == "__main__":
    main()
