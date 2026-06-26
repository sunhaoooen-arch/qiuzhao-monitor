"""抓取层:用 Playwright 渲染页面(让 JS 自己解密/加载),再从 DOM 提取职位。

设计为「按 ATS 配置驱动」:每类招聘系统给一个 profile(等待策略 + 职位链接正则),
一个 profile 覆盖同 ATS 的所有公司。不知道精确 CSS class 时,用「href 匹配职位详情正则」
这种抗改版的通用提取法。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from .models import Job

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


@dataclass
class AtsProfile:
    """一类招聘系统的提取配置。"""
    name: str
    # 渲染后,职位详情链接 href 里能匹配到的正则(用于从一堆 <a> 里挑出职位)
    job_href_re: str
    # 职位列表「路径后缀」:导航前拼到 URL 末尾(如飞书 /position)
    goto_suffix: str = ""
    # 职位列表「hash 路由」:页面(重定向后)用 location.hash 切过去(如 Moka #/jobs)
    hash_route: str = ""
    # 等待超时
    wait_ms: int = 15000
    # 是否需要滚动加载(懒加载列表)
    scroll: bool = True


# 各 ATS 的提取规则。一类一条,覆盖该 ATS 的所有公司。
PROFILES: dict[str, AtsProfile] = {
    "moka":   AtsProfile("moka",   r"/job/|jobId=", hash_route="#/jobs"),
    "feishu": AtsProfile("feishu", r"/position/\d", goto_suffix="/position"),
    "beisen": AtsProfile("beisen", r"/position/|/job/|jobId="),
    "zhilian":AtsProfile("zhilian",r"/job/|position|jobId="),
    "job51":  AtsProfile("job51",  r"/job/|position|jobid="),
    "hotjob": AtsProfile("hotjob", r"/job|position|jobId="),
    "hcm":    AtsProfile("hcm",    r"/job|position|recruit"),
    "iguopin":AtsProfile("iguopin",r"/job|position|/recruit"),
    "generic":AtsProfile("generic",r"job|position|zhaopin|recruit|gw_info"),
}

# 在浏览器里执行:收集页面上所有「看起来是职位」的链接 {title, href, loc}
_COLLECT_JS = r"""
(hrefRe) => {
  const re = new RegExp(hrefRe, 'i');
  const out = [];
  const seen = new Set();      // 按 href 去重:每个职位详情链接只取一次
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.href;
    if (!re.test(href)) continue;
    if (seen.has(href)) continue;
    // 标题取锚文本的「首行」(职位卡片里标题在第一行,后面是日期/公司等元信息)
    const full = (a.innerText || a.textContent || '').trim();
    const title = full.split('\n').map(s => s.trim()).filter(Boolean)[0] || '';
    if (!title || title.length < 2 || title.length > 50) continue;
    seen.add(href);
    // 就近找工作地点(整张卡片文本里的「XX市/区」)
    let loc = '';
    const card = a.closest('li,tr,div') || a;
    const m = (card.innerText || '').match(/[一-龥]{2,8}(市|区)/);
    if (m) loc = m[0];
    out.push({title, href, loc});
  }
  return out;
}
"""


def fetch_company(page, company: dict) -> list[Job]:
    """抓单个公司,返回 Job 列表(未匹配过滤、未去重)。"""
    profile = PROFILES.get(company.get("ats", "generic"), PROFILES["generic"])
    url = company["url"]
    # 路径型列表路由:导航前拼上(避免重复拼)
    if profile.goto_suffix and not url.rstrip("/").endswith(profile.goto_suffix.strip("/")):
        url = url.rstrip("/") + profile.goto_suffix

    # 1) 先打开落地页,等它(可能的)重定向与首屏加载完成
    page.goto(url, wait_until="domcontentloaded", timeout=40000)
    try:
        page.wait_for_load_state("networkidle", timeout=profile.wait_ms)
    except PWTimeout:
        pass
    page.wait_for_timeout(2500)

    # 2) hash 路由 SPA:切到「职位列表」路由(重定向后再切才生效)
    if profile.hash_route:
        page.evaluate("h => { window.location.hash = h }", profile.hash_route.lstrip("#"))
        page.wait_for_timeout(3500)

    # 3) 懒加载列表:滚动到底
    if profile.scroll:
        for _ in range(5):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(900)

    raw_items = page.evaluate(_COLLECT_JS, profile.job_href_re)

    jobs: list[Job] = []
    for it in raw_items:
        jobs.append(Job(
            company=company["name"],
            category=company.get("category", "乙"),
            title=re.sub(r"\s+", " ", it["title"]).strip(),
            url=it["href"],
            location=it.get("loc", ""),
            raw=it["title"],
        ))
    return jobs


class Renderer:
    """封装 Playwright 浏览器生命周期。"""
    def __enter__(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=True)
        self.context = self.browser.new_context(
            user_agent=UA, locale="zh-CN", ignore_https_errors=True,
        )
        return self

    def page(self):
        return self.context.new_page()

    def __exit__(self, *exc):
        self.context.close()
        self.browser.close()
        self._pw.stop()
