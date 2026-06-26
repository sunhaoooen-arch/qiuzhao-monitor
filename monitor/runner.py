"""主流程:加载配置 → 逐家渲染抓取 → 匹配 → 去重 → 分组发邮件。"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import yaml

from .fetcher import Renderer, fetch_company
from .matcher import matches
from .models import Job
from .notifier import send_email
from .storage import Store

CONFIG = Path(__file__).resolve().parent.parent / "companies.yaml"


def load_companies() -> list[dict]:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return [c for c in data.get("companies", []) if c.get("enabled", True)]


def run(send: bool = True, only: str | None = None) -> dict[str, list[Job]]:
    companies = load_companies()
    if only:
        companies = [c for c in companies if c["name"] == only]
    store = Store()
    first_run = store.is_first_run()

    all_current: list[Job] = []   # 本轮抓到的全部匹配岗位(新增+原有在招)
    new_jobs: list[Job] = []      # 其中本轮新增的
    warnings: list[str] = []

    with Renderer() as r:
        for c in companies:
            page = r.page()
            try:
                jobs = fetch_company(page, c)
                matched = [j for j in jobs if matches(j)]
                new = store.filter_new(matched)
                for j in new:
                    j.is_new = True
                all_current.extend(matched)
                new_jobs.extend(new)
                store.record_ok(c["name"])
                print(f"[OK] {c['name']:<14} 抓到 {len(jobs):>3} / 匹配 {len(matched):>3} / 新增 {len(new):>3}")
            except Exception as e:  # noqa
                streak = store.record_fail(c["name"], repr(e))
                print(f"[FAIL] {c['name']}: {e}")
                if streak >= 2:
                    warnings.append(f"{c['name']}（连续失败{streak}次）: {e}")
            finally:
                page.close()

    # 邮件分组:同步「新增 + 原有在招」全部岗位,新增的带 🆕 标记
    grouped: dict[str, list[Job]] = {}
    for j in all_current:
        grouped.setdefault(j.category, []).append(j)

    if first_run:
        print(f"\n[首轮] 建立基线，登记 {len(new_jobs)} 个岗位，本轮不发邮件。")
        store.mark_notified(new_jobs)
        store.close()
        return grouped

    new_count = len(new_jobs)
    # 仅当有「新增」或有抓取告警时才发(避免无变化打扰),但邮件正文同步全部在招岗位
    if send and (new_count > 0 or warnings):
        try:
            send_email(grouped, new_count, warnings)
            store.mark_notified(new_jobs)
            print(f"\n[邮件] 已发送，新增 {new_count}，当前在招 {len(all_current)}。")
        except Exception as e:  # noqa
            print(f"\n[邮件失败] {e}", file=sys.stderr)
            traceback.print_exc()
    else:
        print(f"\n[完成] 新增 {new_count} 个岗位" + ("（未配置发送，跳过邮件）" if not send else "，无需发邮件。"))

    store.close()
    return grouped
