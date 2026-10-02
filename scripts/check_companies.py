#!/usr/bin/env python3
"""试抓公司配置,验证 URL 和提取规则是否能抓到岗位。不读写去重库,不发邮件。

用法:
    python scripts/check_companies.py                      # 试抓 companies.yaml 里全部启用的公司
    python scripts/check_companies.py 九阳股份 海尔卡奥斯   # 只试抓指定公司(含未启用的)
    python scripts/check_companies.py --file x.yaml        # 试抓另一份清单(同格式)
    python scripts/check_companies.py --shard 1/4          # 只跑四分之一(CI 并行用)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitor.fetcher import Renderer, fetch_company  # noqa: E402
from monitor.matcher import matches  # noqa: E402
from monitor.runner import CONFIG  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="只试抓这些公司")
    ap.add_argument("--file", type=Path, default=CONFIG, help="公司清单 yaml")
    ap.add_argument("--shard", default="1/1", help="i/n:只跑第 i 份(共 n 份)")
    args = ap.parse_args()

    companies = yaml.safe_load(args.file.read_text(encoding="utf-8")).get("companies", [])
    if args.names:
        companies = [c for c in companies if c["name"] in args.names]
    else:
        companies = [c for c in companies if c.get("enabled", True)]
    companies = [c for c in companies if c.get("url")]
    i, n = (int(x) for x in args.shard.split("/"))
    companies = companies[i - 1::n]

    with Renderer() as r:
        for c in companies:
            page = r.page()
            try:
                jobs = fetch_company(page, c)
                matched = [j for j in jobs if matches(j)]
                sample = " | ".join(j.title for j in matched[:3])
                print(f"[OK] {c['name']}  抓到 {len(jobs)} / 匹配 {len(matched)}  {c['url']}  {sample}")
            except Exception as e:  # noqa
                print(f"[FAIL] {c['name']}  {c['url']}  {str(e).splitlines()[0]}")
            finally:
                page.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
