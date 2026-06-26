"""数据模型。"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Job:
    """一个抓到的职位。"""
    company: str          # 公司名(配置里的名字)
    category: str         # 甲 / 乙 / 丙
    title: str            # 职位名
    url: str              # 职位详情/投递链接
    location: str = ""    # 工作地点(能抓到就填)
    raw: str = ""         # 原始文本(用于匹配兜底)
    is_new: bool = False  # 是否本轮新增(用于邮件标记 🆕)

    @property
    def fingerprint(self) -> str:
        """稳定指纹,用于去重。同公司同职位名同链接 = 同一个岗位。"""
        key = f"{self.company}||{self.title}||{self.url}".strip().lower()
        return hashlib.sha1(key.encode("utf-8")).hexdigest()

    def haystack(self) -> str:
        """用于关键词匹配的合并文本。"""
        return " ".join([self.title, self.location, self.raw]).lower()
