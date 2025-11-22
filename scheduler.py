#!/usr/bin/env python3
"""定时任务脚本"""

import asyncio
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config
from src.main import main


def run_task():
    """运行任务的包装函数"""
    try:
        logger.info("定时任务触发，开始执行...")
        asyncio.run(main())
        logger.info("定时任务执行完成")
    except Exception as e:
        logger.error(f"定时任务执行失败: {e}", exc_info=True)


def start_scheduler():
    """启动调度器"""
    # 加载配置
    config = get_config()
    
    if not config.scheduler.enabled:
        logger.warning("调度器未启用，程序退出")
        print("调度器未启用，请在配置中启用scheduler.enabled")
        sys.exit(0)
    
    # 创建调度器
    scheduler = BlockingScheduler(timezone=config.scheduler.timezone)
    
    # 解析cron表达式
    # 格式: minute hour day month day_of_week
    cron_parts = config.scheduler.cron.split()
    
    if len(cron_parts) != 5:
        logger.error(f"无效的cron表达式: {config.scheduler.cron}")
        print(f"无效的cron表达式: {config.scheduler.cron}")
        print("格式应为: minute hour day month day_of_week")
        print("例如: 0 9 * * * (每天9点)")
        sys.exit(1)
    
    # 创建cron触发器
    trigger = CronTrigger(
        minute=cron_parts[0],
        hour=cron_parts[1],
        day=cron_parts[2],
        month=cron_parts[3],
        day_of_week=cron_parts[4],
        timezone=config.scheduler.timezone
    )
    
    # 添加任务
    scheduler.add_job(
        run_task,
        trigger=trigger,
        id='book_finder_task',
        name='Book Finder定时任务',
        replace_existing=True
    )
    
    print("=" * 60)
    print("Book Finder - 定时任务模式")
    print("=" * 60)
    print(f"调度表达式: {config.scheduler.cron}")
    print(f"时区: {config.scheduler.timezone}")
    print(f"下次运行时间: {scheduler.get_job('book_finder_task').next_run_time}")
    print("=" * 60)
    print("调度器已启动，按Ctrl+C停止...")
    print()
    
    logger.info(f"调度器已启动，cron表达式: {config.scheduler.cron}")
    
    try:
        # 启动调度器
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("调度器被用户中断")
        print("\n调度器已停止")
        sys.exit(0)
    except Exception as e:
        logger.error(f"调度器异常: {e}", exc_info=True)
        print(f"\n调度器异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    start_scheduler()

