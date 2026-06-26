"""岗位匹配 + 届别过滤。策略:全部从宽(沾边就推),由用户自己再筛。"""
from __future__ import annotations

import re

from .models import Job

# 岗位关键词(从宽)。命中任意一个即视为「匹配」。
DEFAULT_KEYWORDS = [
    "后端", "前端", "全栈", "java", "c++", "python", "golang", " go ", "软件开发",
    "开发工程师", "算法", "机器学习", "深度学习", "ai", "人工智能", "nlp", "cv",
    "计算机视觉", "数据", "大数据", "数据库", "测试", "运维", "客户端", "嵌入式",
    "信息技术", " it ", "技术支持", "解决方案", "网络安全", "信息安全", "云计算",
    "数智", "数字化", "系统工程", "研发", "软件", "程序", "开发",
]

# 明确排除的(非校招/无关方向)。命中即丢弃,优先级高于关键词。
EXCLUDE = [
    "社会招聘", "社招", "实习生招聘",  # 注:实习按用户「校招为主」默认不专门收
]

# 届别正向信号(命中加分,用于判断是不是 2027/校招)
CAMPUS_HINTS = ["校园招聘", "校招", "应届", "2027", "27届", "二七届", "campus", "毕业生", "管培"]


def _norm(text: str) -> str:
    return f" {text.lower()} "


def matches(job: Job, keywords: list[str] | None = None) -> bool:
    """该职位是否值得推送给用户。"""
    kw = keywords or DEFAULT_KEYWORDS
    hay = _norm(job.haystack())

    for bad in EXCLUDE:
        if bad in hay:
            return False

    return any(k.strip() and k in hay for k in kw)


def looks_like_2027(text: str) -> bool:
    """页面/职位文本是否像 2027 届校招。用户要求:校招为主,不确定届别的也推。
    所以这里只用于「标注」,不用于过滤。"""
    hay = _norm(text)
    if "2026" in hay and "2027" not in hay:
        return False  # 明确只是 2026 届的,降权
    return any(h in hay for h in CAMPUS_HINTS)
