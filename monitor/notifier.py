"""邮件通知:把本轮新增+匹配的职位,按甲/乙/丙分组,汇总成一封邮件。"""
from __future__ import annotations

import os
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

from .models import Job

CATEGORY_TITLE = {
    "甲": "甲类 · 山东重点关注",
    "乙": "乙类 · 全国头部大厂",
    "丙": "丙类 · 山东其他热门",
}
ORDER = ["甲", "乙", "丙"]


def _beijing_now() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")


def render_html(grouped: dict[str, list[Job]], new_count: int | None = None) -> str:
    parts = ["<div style='font-family:-apple-system,Helvetica,Arial,sans-serif;font-size:14px;color:#222'>"]
    total = sum(len(v) for v in grouped.values())
    if new_count is None:
        new_count = sum(1 for v in grouped.values() for j in v if j.is_new)

    # 顶部:实时抓取时间 + 本轮新增/当前在招总数
    parts.append(
        "<div style='background:#f5f7fa;border-radius:6px;padding:10px 14px;margin-bottom:14px'>"
        "<h2 style='margin:0 0 6px'>2027届秋招监控</h2>"
        f"<div style='color:#555'>🕐 抓取时间：<b>{_beijing_now()}</b>（北京时间）</div>"
        f"<div style='color:#555'>🆕 本轮新增 <b style='color:#c00'>{new_count}</b> 个 · "
        f"📋 当前在招共 <b>{total}</b> 个（新增与原有一并同步）</div>"
        "</div>"
    )

    for cat in ORDER:
        jobs = grouped.get(cat) or []
        if not jobs:
            continue
        new_in_cat = sum(1 for j in jobs if j.is_new)
        parts.append(f"<h3 style='border-bottom:2px solid #c00;padding-bottom:4px'>"
                     f"{CATEGORY_TITLE.get(cat, cat)}（{len(jobs)}，含新增 {new_in_cat}）</h3>")
        by_co: dict[str, list[Job]] = {}
        for j in jobs:
            by_co.setdefault(j.company, []).append(j)
        for co, items in by_co.items():
            # 新增的排前面
            items.sort(key=lambda x: (not x.is_new, x.title))
            co_new = sum(1 for j in items if j.is_new)
            tag = f" <span style='color:#c00'>🆕{co_new}</span>" if co_new else ""
            parts.append(f"<p style='margin:8px 0 2px'><b>{co}</b>{tag}</p><ul style='margin:0'>")
            for j in items:
                loc = f" · {j.location}" if j.location else ""
                badge = ("<span style='background:#c00;color:#fff;font-size:11px;"
                         "border-radius:3px;padding:0 4px;margin-right:5px'>新</span>") if j.is_new else ""
                style = "font-weight:bold;" if j.is_new else "color:#444;"
                parts.append(
                    f"<li style='{style}'>{badge}<a href='{j.url}'>{j.title}</a>"
                    f"<span style='color:#999;font-weight:normal'>{loc}</span></li>"
                )
            parts.append("</ul>")
    parts.append("<p style='color:#aaa;font-size:12px'>🆕/「新」=本轮新增；其余为仍在招的原有岗位。"
                 "自动抓取，仅供参考，以企业官方为准。</p></div>")
    return "".join(parts)


def send_email(grouped: dict[str, list[Job]], new_count: int | None = None,
               health_warnings: list[str] | None = None) -> None:
    """通过 SMTP 发送。配置全部读环境变量,便于本地 .env 和 GitHub Actions Secrets 复用。"""
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ["SMTP_USER"]          # 发件邮箱
    pwd = os.environ["SMTP_PASS"]           # SMTP 授权码(非登录密码)
    to_addr = os.environ.get("MAIL_TO", user)
    sender_name = os.environ.get("MAIL_FROM_NAME", "秋招监控")

    if new_count is None:
        new_count = sum(1 for v in grouped.values() for j in v if j.is_new)
    html = render_html(grouped, new_count)
    if health_warnings:
        html += "<hr><p style='color:#c60'>⚠ 抓取异常（可能需要修规则）：<br>" + \
                "<br>".join(health_warnings) + "</p>"

    msg = MIMEText(html, "html", "utf-8")
    total = sum(len(v) for v in grouped.values())
    msg["Subject"] = Header(f"【秋招监控】新增 {new_count} · 在招 {total}", "utf-8")
    msg["From"] = formataddr((str(Header(sender_name, "utf-8")), user))
    msg["To"] = to_addr
    recipients = [a.strip() for a in to_addr.split(",")]

    last_err = None
    for attempt in range(1, 4):  # 偶发网络抖动:最多重试 3 次
        try:
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=60)
            else:
                server = smtplib.SMTP(host, port, timeout=60)
                server.starttls()
            server.login(user, pwd)
            server.sendmail(user, recipients, msg.as_string())
            server.quit()
            return
        except Exception as e:  # noqa
            last_err = e
            print(f"[发信重试 {attempt}/3] {e}")
            try:
                server.close()
            except Exception:
                pass
            time.sleep(5)
    raise last_err
