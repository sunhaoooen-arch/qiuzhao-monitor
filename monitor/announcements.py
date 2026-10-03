"""搜索整理的校招公告:由每天的定时搜索写入 data/announcements.yaml,这里读出来并入邮件。

文件格式:
    searched_at: "2026-10-03 08:00"
    announcements:
      - {company: 国家电网, title: "国家电网2027年高校毕业生招聘公告", url: "https://...", date: "2026-09-20"}
    not_found: [中国铁塔, 航天科技]     # 没搜到公告、需要自己去官网查的
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .models import Job

FILE = Path(__file__).resolve().parent.parent / "data" / "announcements.yaml"
CATEGORY = "公告"


def load(path: Path = FILE) -> tuple[list[Job], list[str], str]:
    """返回 (公告列表, 没搜到的公司, 搜索时间)。文件不存在时返回空。"""
    if not path.exists():
        return [], [], ""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    jobs = []
    for a in data.get("announcements") or []:
        if not a.get("title") or not a.get("url"):
            continue
        jobs.append(Job(
            company=str(a.get("company", "")),
            category=CATEGORY,
            title=str(a["title"]).strip(),
            url=str(a["url"]).strip(),
            location=str(a.get("date", "") or ""),
            raw=str(a["title"]),
        ))
    return jobs, [str(c) for c in data.get("not_found") or []], str(data.get("searched_at", "") or "")
