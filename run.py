#!/usr/bin/env python3
"""入口。
用法:
    python run.py                # 正常一轮(抓取→匹配→去重→发邮件)
    python run.py --no-send      # 抓取但不发邮件(调试)
    python run.py --only 中孚信息  # 只跑某一家(调试某家的提取规则)
"""
import argparse
import os
from pathlib import Path

# 读取同目录 .env(简单解析,免装 python-dotenv)
_env = Path(__file__).resolve().parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from monitor.runner import run  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-send", action="store_true", help="不发邮件")
    ap.add_argument("--only", help="只跑指定公司名")
    ap.add_argument("--test-email", action="store_true", help="发一封样例邮件,验证 SMTP 配置")
    args = ap.parse_args()

    if args.test_email:
        from monitor.models import Job
        from monitor.notifier import send_email
        def J(co, cat, t, u, loc, new):  # 便捷构造,new=是否本轮新增
            return Job(co, cat, t, u, loc, is_new=new)
        demo = {
            "甲": [
                J("浪潮集团", "甲", "云计算研发工程师", "https://inspur.hcmcloud.cn/recruit", "济南市", True),
                J("中孚信息", "甲", "服务端开发工程师-Java", "https://join.zhongfu.net/", "济南市", True),
                J("中孚信息", "甲", "安全算法工程师", "https://join.zhongfu.net/", "济南市", False),
                J("歌尔股份", "甲", "嵌入式软件工程师", "https://goertek.hotjob.cn/", "潍坊市", False),
            ],
            "乙": [
                J("奇安信", "乙", "渗透测试工程师（攻防方向）", "https://app.mokahr.com/campus-recruitment/qianxin/29182", "北京市", True),
                J("蔚来", "乙", "校招-AI研究工程师", "https://nio.jobs.feishu.cn/campus", "上海市", False),
                J("智谱", "乙", "大模型算法工程师（校招）", "https://zhipu-ai.jobs.feishu.cn/zhipucampus", "北京市", False),
            ],
            "丙": [
                J("齐鲁制药", "丙", "信息化系统开发工程师", "https://qilu-pharma.zhiye.com/", "济南市", False),
            ],
        }
        send_email(demo)
        print("✅ 测试邮件已发送,去收件箱看看。")
    else:
        run(send=not args.no_send, only=args.only)
