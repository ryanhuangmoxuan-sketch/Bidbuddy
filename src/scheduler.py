"""
BidBuddy — 轻量定时调度器
基于 APScheduler 的简明封装
"""
import logging
from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("BidBuddy.Scheduler")


class TaskScheduler:
    """定时任务调度器"""

    def __init__(self, interval_minutes: int = 30):
        self.interval = interval_minutes
        self._scheduler: Optional[BackgroundScheduler] = None
        self._task: Optional[Callable] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, task: Callable, run_immediately: bool = True):
        """启动定时任务"""
        if self._running:
            return

        self._task = task
        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            task,
            trigger=IntervalTrigger(minutes=self.interval),
            id='bidbuddy_main',
            name='招投标监控主任务',
            replace_existing=True
        )
        self._scheduler.start()
        self._running = True
        logger.info(f"⏰ 定时任务已启动，间隔 {self.interval} 分钟")

        if run_immediately:
            try:
                task()
            except Exception as e:
                logger.error(f"首次执行失败: {e}")

    def stop(self):
        """停止定时任务"""
        if self._scheduler and self._running:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            self._running = False
            logger.info("⏹️ 定时任务已停止")

    def update_interval(self, minutes: int):
        """更新执行间隔"""
        self.interval = minutes
        if self._scheduler and self._running:
            self._scheduler.reschedule_job(
                'bidbuddy_main',
                trigger=IntervalTrigger(minutes=minutes)
            )
            logger.info(f"⏱️ 间隔已更新为 {minutes} 分钟")
