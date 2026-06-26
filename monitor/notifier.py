"""邮件通知:把本轮新增+匹配的职位,按甲/乙/丙分组,汇总成一封邮件。"""
from __future__ import annotations

import os
import smtplib
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


def render_html(grouped: dict[str, list[Job]]) -> str:
    parts = ["<div style='font-family:-apple-system,Helvetica,Arial,sans-serif;font-size:14px'>"]
    total = sum(len(v) for v in grouped.values())
    parts.append(f"<h2>2027届秋招监控 · 本轮新增 {total} 个匹配岗位</h2>")
    for cat in ORDER:
        jobs = grouped.get(cat) or []
        if not jobs:
            continue
        parts.append(f"<h3 style='border-bottom:2px solid #c00;padding-bottom:4px'>"
                     f"{CATEGORY_TITLE.get(cat, cat)}（{len(jobs)}）</h3>")
        # 同类里按公司聚合
        by_co: dict[str, list[Job]] = {}
        for j in jobs:
            by_co.setdefault(j.company, []).append(j)
        for co, items in by_co.items():
            parts.append(f"<p style='margin:8px 0 2px'><b>{co}</b></p><ul style='margin:0'>")
            for j in items:
                loc = f" · {j.location}" if j.location else ""
                parts.append(
                    f"<li><a href='{j.url}'>{j.title}</a>"
                    f"<span style='color:#888'>{loc}</span></li>"
                )
            parts.append("</ul>")
    parts.append("<p style='color:#aaa;font-size:12px'>— 自动抓取，仅供参考，以企业官方为准。</p></div>")
    return "".join(parts)


def send_email(grouped: dict[str, list[Job]], health_warnings: list[str] | None = None) -> None:
    """通过 SMTP 发送。配置全部读环境变量,便于本地 .env 和 GitHub Actions Secrets 复用。"""
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ["SMTP_USER"]          # 发件邮箱
    pwd = os.environ["SMTP_PASS"]           # SMTP 授权码(非登录密码)
    to_addr = os.environ.get("MAIL_TO", user)
    sender_name = os.environ.get("MAIL_FROM_NAME", "秋招监控")

    html = render_html(grouped)
    if health_warnings:
        html += "<hr><p style='color:#c60'>⚠ 抓取异常（可能需要修规则）：<br>" + \
                "<br>".join(health_warnings) + "</p>"

    msg = MIMEText(html, "html", "utf-8")
    total = sum(len(v) for v in grouped.values())
    msg["Subject"] = Header(f"【秋招监控】本轮新增 {total} 个岗位", "utf-8")
    msg["From"] = formataddr((str(Header(sender_name, "utf-8")), user))
    msg["To"] = to_addr

    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
        server.starttls()
    server.login(user, pwd)
    server.sendmail(user, [a.strip() for a in to_addr.split(",")], msg.as_string())
    server.quit()
