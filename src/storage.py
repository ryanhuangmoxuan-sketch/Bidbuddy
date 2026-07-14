"""
BidBuddy — 轻量JSON文件存储
简洁的数据持久化方案，使用JSON文件存储招标信息
"""
import json
import os
import threading
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class BidItem:
    """招标信息条目"""
    title: str
    url: str
    source: str
    content: str = ""
    publish_date: Optional[str] = None
    notified: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def id(self) -> str:
        """生成唯一ID"""
        import hashlib
        raw = f"{self.title}|{self.url}|{self.source}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]


class Storage:
    """JSON文件存储引擎"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        self.data_dir = data_dir
        self.data_file = os.path.join(data_dir, 'bids.json')
        self._lock = threading.Lock()
        os.makedirs(data_dir, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.data_file):
            self._write([])

    def _read(self) -> List[dict]:
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, data: List[dict]):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def exists(self, bid: BidItem) -> bool:
        bid_id = bid.id
        data = self._read()
        return any(self._item_id(item) == bid_id for item in data)

    def save(self, bid: BidItem, notified: bool = False):
        with self._lock:
            data = self._read()
            bid.notified = notified
            data.append(asdict(bid))
            self._write(data)

    def mark_notified(self, bid: BidItem):
        with self._lock:
            data = self._read()
            bid_id = bid.id
            for item in data:
                if self._item_id(item) == bid_id:
                    item['notified'] = True
            self._write(data)

    def get_all(self) -> List[BidItem]:
        data = self._read()
        return [self._dict_to_bid(item) for item in data]

    def get_unnotified(self) -> List[BidItem]:
        data = self._read()
        return [self._dict_to_bid(item) for item in data if not item.get('notified', False)]

    def count_all(self) -> int:
        return len(self._read())

    def clear_all(self):
        with self._lock:
            self._write([])

    @staticmethod
    def _item_id(item: dict) -> str:
        import hashlib
        raw = f"{item.get('title', '')}|{item.get('url', '')}|{item.get('source', '')}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    @staticmethod
    def _dict_to_bid(d: dict) -> BidItem:
        return BidItem(
            title=d.get('title', ''),
            url=d.get('url', ''),
            source=d.get('source', ''),
            content=d.get('content', ''),
            publish_date=d.get('publish_date'),
            notified=d.get('notified', False),
            created_at=d.get('created_at', '')
        )
