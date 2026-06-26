"""SQLite 存储:记录已见过/已推送的职位,实现去重。"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .models import Job

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "qiuzhao.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    fingerprint TEXT PRIMARY KEY,
    company     TEXT,
    category    TEXT,
    title       TEXT,
    url         TEXT,
    location    TEXT,
    first_seen  INTEGER,
    notified    INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fetch_health (
    company      TEXT PRIMARY KEY,
    last_ok      INTEGER,
    last_error   TEXT,
    fail_streak  INTEGER DEFAULT 0
);
"""


class Store:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- 职位去重 ----
    def filter_new(self, jobs: list[Job]) -> list[Job]:
        """返回从未入库过的职位(本轮新增),并把它们登记为已见(notified=0)。"""
        new = []
        cur = self.conn.cursor()
        now = int(time.time())
        for j in jobs:
            fp = j.fingerprint
            row = cur.execute("SELECT 1 FROM seen_jobs WHERE fingerprint=?", (fp,)).fetchone()
            if row:
                continue
            cur.execute(
                "INSERT OR IGNORE INTO seen_jobs"
                "(fingerprint,company,category,title,url,location,first_seen,notified)"
                " VALUES (?,?,?,?,?,?,?,0)",
                (fp, j.company, j.category, j.title, j.url, j.location, now),
            )
            new.append(j)
        self.conn.commit()
        return new

    def mark_notified(self, jobs: list[Job]) -> None:
        cur = self.conn.cursor()
        for j in jobs:
            cur.execute("UPDATE seen_jobs SET notified=1 WHERE fingerprint=?", (j.fingerprint,))
        self.conn.commit()

    def is_first_run(self) -> bool:
        row = self.conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()
        return row[0] == 0

    # ---- 抓取健康度 ----
    def record_ok(self, company: str) -> None:
        now = int(time.time())
        self.conn.execute(
            "INSERT INTO fetch_health(company,last_ok,last_error,fail_streak) VALUES(?,?,'',0) "
            "ON CONFLICT(company) DO UPDATE SET last_ok=?, last_error='', fail_streak=0",
            (company, now, now),
        )
        self.conn.commit()

    def record_fail(self, company: str, err: str) -> int:
        self.conn.execute(
            "INSERT INTO fetch_health(company,last_ok,last_error,fail_streak) VALUES(?,NULL,?,1) "
            "ON CONFLICT(company) DO UPDATE SET last_error=?, fail_streak=fail_streak+1",
            (company, err, err),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT fail_streak FROM fetch_health WHERE company=?", (company,)
        ).fetchone()
        return row[0] if row else 1

    def close(self) -> None:
        self.conn.close()
