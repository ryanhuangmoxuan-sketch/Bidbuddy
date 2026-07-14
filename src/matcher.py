"""
BidBuddy — 关键词匹配器
支持 AND/OR/NOT 逻辑的多关键词匹配
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class MatchResult:
    """匹配结果"""
    matched: bool = False
    matched_keywords: List[str] = field(default_factory=list)
    excluded_by: str = ""


class KeywordMatcher:
    """
    智能关键词匹配器

    匹配逻辑（AND/OR 组合）：
    1. OR 组（include_keywords）：标题或内容命中任意一个即进入候选
    2. AND 组（must_contain_keywords）：所有AND词都必须命中才最终匹配
    3. NOT 组（exclude_keywords）：命中任意一个排除词则直接丢弃
    """

    def __init__(
        self,
        include_keywords: List[str] = None,
        exclude_keywords: List[str] = None,
        must_contain_keywords: List[str] = None
    ):
        self.include = [k.lower().strip() for k in (include_keywords or []) if k.strip()]
        self.exclude = [k.lower().strip() for k in (exclude_keywords or []) if k.strip()]
        self.must_contain = [k.lower().strip() for k in (must_contain_keywords or []) if k.strip()]

    def match_any(self, title: str = "", content: str = "") -> MatchResult:
        """执行匹配"""
        text = f"{title or ''} {content or ''}".lower()

        # Step 1: NOT 排除检查
        for kw in self.exclude:
            if kw and kw in text:
                return MatchResult(matched=False, excluded_by=kw)

        # Step 2: OR 命中检查
        matched_or = []
        for kw in self.include:
            if kw and kw in text:
                matched_or.append(kw)

        if not matched_or:
            return MatchResult(matched=False)

        # Step 3: AND 必须包含检查
        for kw in self.must_contain:
            if kw and kw not in text:
                return MatchResult(matched=False)

        return MatchResult(matched=True, matched_keywords=matched_or)
