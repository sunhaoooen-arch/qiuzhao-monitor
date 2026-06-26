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

    all_new: list[Job] = []
    warnings: list[str] = []

    with Renderer() as r:
        for c in companies:
            page = r.page()
            try:
                jobs = fetch_company(page, c)
                matched = [j for j in jobs if matches(j)]
                new = store.filter_new(matched)
                all_new.extend(new)
                store.record_ok(c["name"])
                print(f"[OK] {c['name']:<14} 抓到 {len(jobs):>3} / 匹配 {len(matched):>3} / 新增 {len(new):>3}")
            except Exception as e:  # noqa
                streak = store.record_fail(c["name"], repr(e))
                print(f"[FAIL] {c['name']}: {e}")
                if streak >= 2:
                    warnings.append(f"{c['name']}（连续失败{streak}次）: {e}")
            finally:
                page.close()

    grouped: dict[str, list[Job]] = {}
    for j in all_new:
        grouped.setdefault(j.category, []).append(j)

    if first_run:
        print(f"\n[首轮] 建立基线，登记 {len(all_new)} 个岗位，本轮不发邮件。")
        store.mark_notified(all_new)
        store.close()
        return grouped

    total = len(all_new)
    if send and (total > 0 or warnings):
        try:
            send_email(grouped, warnings)
            store.mark_notified(all_new)
            print(f"\n[邮件] 已发送，新增 {total} 个岗位。")
        except Exception as e:  # noqa
            print(f"\n[邮件失败] {e}", file=sys.stderr)
            traceback.print_exc()
    else:
        print(f"\n[完成] 新增 {total} 个岗位" + ("（未配置发送，跳过邮件）" if not send else "，无需发邮件。"))

    store.close()
    return grouped
