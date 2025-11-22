"""主流程编排模块"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from loguru import logger

from .config import get_config, Config
from .notion_client import NotionBookClient, Book
from .weread_api import WeReadAPIClient
from .llm_analyzer import LLMAnalyzer
from .notifier import Notifier, NotificationMessage


class BookFinderApp:
    """书籍查找应用主类"""
    
    def __init__(self, config: Config):
        self.config = config
        self.notion_client = NotionBookClient(config.notion)
        self.llm_analyzer = LLMAnalyzer(config.llm)
        self.notifier = Notifier(config.notification)
        
        # 初始化日志
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志"""
        # 移除默认的处理器
        logger.remove()
        
        # 添加控制台输出
        logger.add(
            sys.stdout,
            format=self.config.logging.format,
            level=self.config.logging.level,
            colorize=True
        )
        
        # 添加文件输出
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logger.add(
            log_dir / "book_finder_{time:YYYY-MM-DD}.log",
            format=self.config.logging.format,
            level=self.config.logging.level,
            rotation=self.config.logging.rotation,
            retention=self.config.logging.retention,
            encoding="utf-8"
        )
        
        logger.info("日志系统初始化完成")
    
    def run(self):
        """运行主流程"""
        try:
            logger.info("=" * 60)
            logger.info("开始书籍查找任务")
            logger.info("=" * 60)
            
            start_time = datetime.now()
            
            # 1. 从Notion获取书籍列表
            logger.info("步骤 1/5: 从Notion获取书籍列表")
            books = self.notion_client.get_books_to_check()
            
            if not books:
                logger.warning("没有找到待检查的书籍")
                return
            
            logger.info(f"找到 {len(books)} 本待检查的书籍")
            
            # 2. 使用微信读书API搜索
            logger.info("步骤 2/5: 在微信读书上搜索书籍")
            search_results = self._search_books_sync(books)
            
            # 3. 使用LLM分析搜索结果
            logger.info("步骤 3/5: 使用LLM分析搜索结果")
            analysis_results = self._analyze_results(books, search_results)
            
            # 4. 更新Notion状态
            logger.info("步骤 4/5: 更新Notion数据库")
            update_stats = self._update_notion(books, search_results, analysis_results)
            
            # 5. 发送通知
            logger.info("步骤 5/5: 发送通知")
            self._send_notification(books, analysis_results, update_stats)
            
            # 统计信息
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info("=" * 60)
            logger.info(f"任务完成！耗时: {duration:.2f} 秒")
            logger.info(f"总书籍数: {len(books)}")
            logger.info(f"已上架: {sum(1 for r in analysis_results if r.is_available)}")
            logger.info(f"未上架: {sum(1 for r in analysis_results if not r.is_available)}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"任务执行失败: {e}", exc_info=True)
            raise
    
    def _search_books_sync(self, books: List[Book]) -> List[Any]:
        """搜索书籍（同步版本，使用API）"""
        search_results = []
        
        # 使用API客户端搜索
        api_client = WeReadAPIClient(self.config.crawler)
        
        for i, book in enumerate(books, 1):
            logger.info(f"[{i}/{len(books)}] 搜索: {book.title}")
            
            try:
                # 先用LLM生成优化的搜索关键词
                keywords_result = self.llm_analyzer.generate_search_keywords(
                    book_title=book.title,
                    author=book.author
                )
                
                # 使用生成的关键词进行搜索
                result = api_client.search_book(
                    book_title=book.title,
                    author=book.author,
                    custom_keywords=keywords_result.keywords
                )
                search_results.append(result)
                
                if result.has_results:
                    logger.info(f"  ✓ 找到 {len(result.found_books)} 个结果")
                else:
                    logger.warning(f"  ✗ 未找到结果")
            
            except Exception as e:
                logger.error(f"  ✗ 搜索失败: {e}")
                # 创建一个错误结果
                from .weread_api import WeReadSearchResult
                search_results.append(
                    WeReadSearchResult(
                        book_title=book.title,
                        search_keyword=book.title,
                        found_books=[],
                        error=str(e),
                        attempted_keywords=[book.title]
                    )
                )
            
            # 控制请求速率
            if i < len(books):  # 不是最后一本
                import time
                time.sleep(2)  # 每本书之间等待2秒
        
        return search_results
    
    def _analyze_results(self, books: List[Book], search_results: List[Any]) -> List[Any]:
        """分析搜索结果"""
        analysis_results = []
        
        for i, (book, search_result) in enumerate(zip(books, search_results), 1):
            logger.info(f"[{i}/{len(books)}] 分析: {book.title}")
            
            try:
                result = self.llm_analyzer.analyze_search_result(
                    book_title=book.title,
                    search_result=search_result,
                    author=book.author
                )
                analysis_results.append(result)
                
                if result.is_available:
                    logger.info(f"  ✓ 已上架 (置信度: {result.confidence:.2f})")
                    if result.matched_title:
                        logger.info(f"    匹配书名: {result.matched_title}")
                else:
                    logger.info(f"  ✗ 未上架")
                
                if result.reasoning:
                    logger.debug(f"    理由: {result.reasoning}")
            
            except Exception as e:
                logger.error(f"  ✗ 分析失败: {e}")
                # 创建一个错误结果
                from .llm_analyzer import BookAnalysisResult
                analysis_results.append(
                    BookAnalysisResult(
                        book_title=book.title,
                        is_available=False,
                        confidence=0.0,
                        reasoning=f"分析失败: {str(e)}",
                        error=str(e)
                    )
                )
        
        return analysis_results
    
    def _update_notion(
        self,
        books: List[Book],
        search_results: List[Any],
        analysis_results: List[Any]
    ) -> Dict[str, int]:
        """更新Notion数据库"""
        stats = {
            "success": 0,
            "failed": 0
        }
        
        for book, search_result, analysis_result in zip(books, search_results, analysis_results):
            try:
                # 构建备注信息
                notes = None
                if analysis_result.reasoning:
                    notes = analysis_result.reasoning
                elif analysis_result.error:
                    notes = f"错误: {analysis_result.error}"
                
                # 使用所有尝试过的关键词，用逗号分隔
                all_keywords = ", ".join(search_result.attempted_keywords)
                
                success = self.notion_client.update_book_status(
                    page_id=book.page_id,
                    available=analysis_result.is_available,
                    search_keywords=all_keywords,
                    notes=notes
                )
                
                if success:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
            
            except Exception as e:
                logger.error(f"更新Notion失败 ({book.title}): {e}")
                stats["failed"] += 1
        
        logger.info(f"Notion更新完成: 成功 {stats['success']}, 失败 {stats['failed']}")
        return stats
    
    def _send_notification(
        self,
        books: List[Book],
        analysis_results: List[Any],
        update_stats: Dict[str, int]
    ):
        """发送通知"""
        # 统计信息
        total_books = len(books)
        available_books = sum(1 for r in analysis_results if r.is_available)
        unavailable_books = total_books - available_books
        
        # 找出新上架的书籍（这里简化处理，实际应该对比之前的状态）
        newly_available = []
        for book, result in zip(books, analysis_results):
            if result.is_available and result.confidence > 0.7:
                newly_available.append({
                    'title': book.title,
                    'author': book.author or '',
                    'matched_title': result.matched_title or book.title
                })
        
        # 找出检查失败的书籍
        failed_books = []
        for book, result in zip(books, analysis_results):
            if result.error:
                failed_books.append({
                    'title': book.title,
                    'error': result.error
                })
        
        # 构建通知消息
        message = NotificationMessage(
            total_books=total_books,
            available_books=available_books,
            unavailable_books=unavailable_books,
            newly_available=newly_available,
            failed_books=failed_books,
            check_time=datetime.now()
        )
        
        # 发送通知
        self.notifier.send(message)


def main():
    """主函数"""
    try:
        # 加载配置
        config = get_config()
        
        # 创建应用实例
        app = BookFinderApp(config)
        
        # 运行主流程
        app.run()
        
    except KeyboardInterrupt:
        logger.info("用户中断任务")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

