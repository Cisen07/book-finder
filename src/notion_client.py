"""Notion API集成模块"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from loguru import logger
from notion_client import Client
from notion_client.errors import APIResponseError

from .config import NotionConfig


class Book:
    """书籍数据模型"""
    
    def __init__(
        self,
        page_id: str,
        title: str,
        title_en: Optional[str] = None,
        author: Optional[str] = None,
        isbn: Optional[str] = None,
        status: Optional[str] = None,
        last_check: Optional[datetime] = None,
        available: Optional[bool] = None,
        search_keywords: Optional[str] = None,
        raw_properties: Optional[Dict[str, Any]] = None
    ):
        self.page_id = page_id
        self.title = title
        self.title_en = title_en
        self.author = author
        self.isbn = isbn
        self.status = status
        self.last_check = last_check
        self.available = available
        self.search_keywords = search_keywords
        self.raw_properties = raw_properties or {}

    def __repr__(self):
        return f"Book(title={self.title}, author={self.author}, available={self.available})"


class NotionBookClient:
    """Notion书籍数据库客户端"""
    
    def __init__(self, config: NotionConfig):
        self.config = config
        self.client = Client(auth=config.api_token)
        self.database_id = config.database_id
    
    def _extract_text_from_property(self, prop: Dict[str, Any]) -> Optional[str]:
        """从属性中提取文本值"""
        try:
            prop_type = prop.get("type")
            
            if prop_type == "title":
                title_list = prop.get("title", [])
                if title_list:
                    return "".join([t.get("plain_text", "") for t in title_list])
            
            elif prop_type == "rich_text":
                rich_text_list = prop.get("rich_text", [])
                if rich_text_list:
                    return "".join([t.get("plain_text", "") for t in rich_text_list])
            
            elif prop_type == "select":
                select = prop.get("select")
                if select:
                    return select.get("name")
            
            elif prop_type == "checkbox":
                return str(prop.get("checkbox", False))
            
            elif prop_type == "date":
                date = prop.get("date")
                if date:
                    return date.get("start")
            
            elif prop_type == "number":
                return str(prop.get("number", ""))
            
            return None
        except Exception as e:
            logger.warning(f"提取属性值失败: {e}")
            return None
    
    def _parse_book_from_page(self, page: Dict[str, Any]) -> Book:
        """从Notion页面解析书籍信息"""
        properties = page.get("properties", {})
        page_id = page.get("id", "")
        
        # 尝试多种可能的属性名称
        title_candidates = ["书名", "名称", "Name", "Title", "书籍名称"]
        author_candidates = ["作者", "Author", "作者名"]
        isbn_candidates = ["ISBN", "isbn"]
        status_candidates = ["状态", "Status", "阅读状态"]
        last_check_candidates = ["最后检查时间", "Last Check", "检查时间"]
        available_candidates = ["已上架", "Available", "微信读书可用"]
        keywords_candidates = ["搜索关键词", "Keywords", "关键词"]
        notes_candidates = ["备注", "Notes", "说明"]
        
        # 提取书名（必需）
        title = None
        for key in title_candidates:
            if key in properties:
                title = self._extract_text_from_property(properties[key])
                if title:
                    break
        
        if not title:
            # 如果没有找到标准的书名字段，使用页面标题
            title = page.get("title", [{}])[0].get("plain_text", "未知书名")
        
        # 提取其他字段
        author = None
        for key in author_candidates:
            if key in properties:
                author = self._extract_text_from_property(properties[key])
                if author:
                    break
        
        isbn = None
        for key in isbn_candidates:
            if key in properties:
                isbn = self._extract_text_from_property(properties[key])
                if isbn:
                    break
        
        status = None
        for key in status_candidates:
            if key in properties:
                status = self._extract_text_from_property(properties[key])
                if status:
                    break
        
        last_check_str = None
        for key in last_check_candidates:
            if key in properties:
                last_check_str = self._extract_text_from_property(properties[key])
                if last_check_str:
                    break
        
        last_check = None
        if last_check_str:
            try:
                last_check = datetime.fromisoformat(last_check_str.replace("Z", "+00:00"))
            except:
                pass
        
        available_str = None
        for key in available_candidates:
            if key in properties:
                available_str = self._extract_text_from_property(properties[key])
                if available_str:
                    break
        
        available = None
        if available_str is not None:
            available = available_str.lower() in ["true", "yes", "1"]
        
        search_keywords = None
        for key in keywords_candidates:
            if key in properties:
                search_keywords = self._extract_text_from_property(properties[key])
                if search_keywords:
                    break
        
        notes = None
        for key in notes_candidates:
            if key in properties:
                notes = self._extract_text_from_property(properties[key])
                if notes:
                    break
        
        return Book(
            page_id=page_id,
            title=title,
            title_en=None,  # 不再使用英文名
            author=author,
            isbn=isbn,
            status=status,
            last_check=last_check,
            available=available,
            search_keywords=search_keywords,
            raw_properties=properties
        )
    
    def get_books_to_check(self, filter_status: Optional[str] = None, skip_available: bool = True) -> List[Book]:
        """
        获取待检查的书籍列表
        
        Args:
            filter_status: 过滤状态（如"想读"）
            skip_available: 是否跳过已上架的书籍
        
        Returns:
            书籍列表
        """
        try:
            logger.info(f"从Notion获取书籍列表，database_id={self.database_id}")
            
            # 构建查询过滤器
            query_filter = None
            if filter_status:
                # 尝试构建状态过滤器
                query_filter = {
                    "property": "状态",
                    "select": {
                        "equals": filter_status
                    }
                }
            
            # 查询数据库（新API使用data_sources.query）
            if query_filter:
                response = self.client.data_sources.query(
                    data_source_id=self.database_id,
                    filter=query_filter
                )
            else:
                response = self.client.data_sources.query(
                    data_source_id=self.database_id
                )
            
            # 解析结果
            books = []
            skipped_count = 0
            for page in response.get("results", []):
                try:
                    book = self._parse_book_from_page(page)
                    
                    # 如果需要跳过已上架的书籍
                    if skip_available and book.available is True:
                        logger.debug(f"跳过已上架的书籍: {book.title}")
                        skipped_count += 1
                        continue
                    
                    books.append(book)
                except Exception as e:
                    logger.error(f"解析书籍页面失败: {e}")
                    continue
            
            if skipped_count > 0:
                logger.info(f"跳过{skipped_count}本已上架的书籍")
            logger.info(f"成功获取{len(books)}本待检查书籍")
            return books
            
        except APIResponseError as e:
            logger.error(f"Notion API错误: {e}")
            raise
        except Exception as e:
            logger.error(f"获取书籍列表失败: {e}")
            raise
    
    def update_book_status(
        self,
        page_id: str,
        available: bool,
        search_keywords: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        更新书籍状态
        
        Args:
            page_id: 页面ID
            available: 是否已上架
            search_keywords: 搜索使用的关键词
            notes: 备注信息（如LLM的分析理由）
        
        Returns:
            是否更新成功
        """
        try:
            logger.info(f"更新书籍状态: page_id={page_id}, available={available}")
            
            # 构建更新属性
            properties = {}
            
            # 更新已上架状态
            for key in ["已上架", "Available", "微信读书可用"]:
                properties[key] = {"checkbox": available}
                break  # 只更新第一个匹配的字段
            
            # 更新最后检查时间
            now = datetime.now().isoformat()
            for key in ["最后检查时间", "Last Check", "检查时间"]:
                properties[key] = {"date": {"start": now}}
                break
            
            # 更新搜索关键词
            if search_keywords:
                for key in ["搜索关键词", "Keywords", "关键词"]:
                    properties[key] = {
                        "rich_text": [{"text": {"content": search_keywords}}]
                    }
                    break
            
            # 更新备注信息
            if notes:
                for key in ["备注", "Notes", "说明"]:
                    properties[key] = {
                        "rich_text": [{"text": {"content": notes}}]
                    }
                    break
            
            # 执行更新
            self.client.pages.update(
                page_id=page_id,
                properties=properties
            )
            
            logger.info(f"书籍状态更新成功: page_id={page_id}")
            return True
            
        except APIResponseError as e:
            logger.error(f"Notion API错误: {e}")
            return False
        except Exception as e:
            logger.error(f"更新书籍状态失败: {e}")
            return False
    
    def list_databases(self) -> List[Dict[str, Any]]:
        """列出所有可访问的数据库（用于调试）"""
        try:
            logger.info("开始搜索Notion数据库...")
            
            # Notion API 更新后，需要搜索所有内容，然后手动过滤数据库
            response = self.client.search()
            
            logger.debug(f"API响应keys: {response.keys()}")
            
            all_results = response.get("results", [])
            logger.info(f"搜索返回总共{len(all_results)}个对象")
            
            # 打印每个对象的类型
            for idx, item in enumerate(all_results):
                obj_type = item.get("object")
                item_id = item.get("id")
                logger.debug(f"对象 {idx+1}: type={obj_type}, id={item_id}")
                
                # 如果是page，尝试获取标题
                if obj_type == "page":
                    page_title = ""
                    props = item.get("properties", {})
                    # 尝试找到标题属性
                    for prop_name, prop_value in props.items():
                        if prop_value.get("type") == "title":
                            title_list = prop_value.get("title", [])
                            if title_list:
                                page_title = "".join([t.get("plain_text", "") for t in title_list])
                                break
                    logger.debug(f"  页面标题: {page_title}")
                
                # 如果是database，尝试获取标题
                elif obj_type == "database":
                    db_title = ""
                    if "title" in item:
                        title_list = item["title"]
                        if title_list:
                            db_title = "".join([t.get("plain_text", "") for t in title_list])
                    logger.debug(f"  数据库标题: {db_title}")
            
            # 过滤出数据库类型的对象（新API返回的是data_source类型）
            databases = [item for item in all_results if item.get("object") in ["database", "data_source"]]
            
            logger.info(f"找到{len(databases)}个数据库")
            for db in databases:
                title = ""
                obj_type = db.get("object")
                
                # 处理不同类型的标题结构
                if "title" in db:
                    title_list = db["title"]
                    if title_list:
                        title = "".join([t.get("plain_text", "") for t in title_list])
                
                # 如果是data_source，可能有不同的结构
                if not title and obj_type == "data_source":
                    # 尝试从properties中获取
                    if "properties" in db:
                        for prop_name, prop_value in db["properties"].items():
                            if prop_value.get("type") == "title":
                                title_list = prop_value.get("title", [])
                                if title_list:
                                    title = "".join([t.get("plain_text", "") for t in title_list])
                                    break
                
                logger.info(f"数据库 ({obj_type}): {title or '(无标题)'} (ID: {db.get('id')})")
            
            return databases
        except Exception as e:
            logger.error(f"列出数据库失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

