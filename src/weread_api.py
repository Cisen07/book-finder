"""微信读书API客户端（替代爬虫）"""

import time
import random
from typing import List, Dict, Optional
import urllib.parse

import requests
from loguru import logger

from .config import CrawlerConfig


class WeReadSearchResult:
    """微信读书搜索结果"""
    
    def __init__(
        self,
        book_title: str,
        search_keyword: str,
        found_books: List[Dict[str, str]],
        total_count: int = 0,
        error: Optional[str] = None
    ):
        self.book_title = book_title
        self.search_keyword = search_keyword
        self.found_books = found_books
        self.total_count = total_count
        self.error = error
        self.has_results = len(found_books) > 0
        # 保留兼容性字段
        self.html_content = ""
        self.page_url = ""

    def __repr__(self):
        return f"WeReadSearchResult(keyword={self.search_keyword}, results={len(self.found_books)}, has_error={self.error is not None})"


class WeReadAPIClient:
    """微信读书API客户端"""
    
    # 微信读书搜索API
    SEARCH_API_URL = "https://weread.qq.com/web/search/global"
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://weread.qq.com/'
        })
    
    def _random_delay(self):
        """随机延迟"""
        delay = random.uniform(self.config.delay_min, self.config.delay_max)
        time.sleep(delay)
    
    def search_book(
        self,
        book_title: str,
        author: Optional[str] = None,
        custom_keywords: Optional[List[str]] = None
    ) -> WeReadSearchResult:
        """
        搜索书籍
        
        Args:
            book_title: 书名
            author: 作者
            custom_keywords: 自定义搜索关键词列表（如果提供，将优先使用）
        
        Returns:
            搜索结果
        """
        # 使用自定义关键词或构建默认关键词列表
        if custom_keywords:
            search_keywords = custom_keywords
            logger.info(f"使用LLM生成的 {len(custom_keywords)} 个关键词搜索")
        else:
            search_keywords = [book_title]
            if author:
                search_keywords.append(f"{book_title} {author}")
        
        last_error = None
        
        # 尝试不同的关键词
        for keyword in search_keywords:
            retry_count = 0
            
            while retry_count < self.config.max_retries:
                try:
                    logger.info(f"搜索书籍: {keyword} (尝试 {retry_count + 1}/{self.config.max_retries})")
                    
                    # 构建搜索URL
                    params = {'keyword': keyword}
                    
                    # 发起请求
                    response = self.session.get(
                        self.SEARCH_API_URL,
                        params=params,
                        timeout=self.config.timeout / 1000  # 转换为秒
                    )
                    
                    # 检查响应
                    if response.status_code == 200:
                        # 解析JSON响应
                        data = response.json()
                        
                        # 提取书籍列表
                        books = data.get('books', [])
                        total_count = data.get('totalCount', 0)
                        
                        logger.info(f"API返回: 找到 {len(books)} 本书籍，总计 {total_count} 本")
                        
                        # 转换为标准格式
                        found_books = []
                        for book_data in books[:10]:  # 只取前10个结果
                            book_info = book_data.get('bookInfo', {})
                            
                            # 判断书籍状态
                            book_status = book_info.get('bookStatus', None)
                            soldout = book_info.get('soldout', 0)
                            
                            # 确定可读状态
                            if book_status == 1 and soldout == 0:
                                availability_status = "已上架可阅读"
                            elif book_status == 5 or soldout == 1:
                                availability_status = "待上架（可订阅但不可阅读）"
                            else:
                                availability_status = f"未知状态(bookStatus={book_status}, soldout={soldout})"
                            
                            found_books.append({
                                'title': book_info.get('title', ''),
                                'author': book_info.get('author', ''),
                                'book_id': book_info.get('bookId', ''),
                                'intro': book_info.get('intro', ''),
                                'publisher': book_info.get('publisher', ''),
                                'availability_status': availability_status,  # 可读状态（人类可读）
                                # 原始状态字段
                                'book_status': book_status,
                                'pay_type': book_info.get('payType', None),
                                'soldout': soldout,
                                'ispub': book_info.get('ispub', None),
                                'finished': book_info.get('finished', None),
                                'price': book_info.get('price', None),
                            })
                        
                        # 如果找到结果，直接返回
                        if found_books:
                            logger.info(f"使用关键词 '{keyword}' 找到 {len(found_books)} 个结果")
                            return WeReadSearchResult(
                                book_title=book_title,
                                search_keyword=keyword,
                                found_books=found_books,
                                total_count=total_count
                            )
                        
                        # 如果没有找到结果，尝试下一个关键词
                        logger.info(f"使用关键词 '{keyword}' 未找到结果，尝试下一个关键词")
                        break
                    
                    else:
                        logger.warning(f"API返回状态码: {response.status_code}")
                        last_error = f"HTTP {response.status_code}"
                        retry_count += 1
                        
                        if retry_count < self.config.max_retries:
                            self._random_delay()
                    
                except requests.RequestException as e:
                    logger.warning(f"请求失败: {e}")
                    last_error = str(e)
                    retry_count += 1
                    
                    if retry_count < self.config.max_retries:
                        self._random_delay()
                
                except Exception as e:
                    logger.error(f"搜索过程出错: {e}")
                    last_error = str(e)
                    retry_count += 1
                    
                    if retry_count < self.config.max_retries:
                        self._random_delay()
        
        # 所有关键词都尝试失败
        logger.error(f"所有搜索关键词都失败: {book_title}")
        return WeReadSearchResult(
            book_title=book_title,
            search_keyword=search_keywords[0],
            found_books=[],
            error=last_error or "未找到搜索结果"
        )

