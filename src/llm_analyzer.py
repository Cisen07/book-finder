"""LLM分析模块"""

import json
from typing import Dict, Any, Optional, List

from loguru import logger
from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError

from .config import LLMConfig
from .weread_api import WeReadSearchResult


class BookAnalysisResult:
    """书籍分析结果"""
    
    def __init__(
        self,
        book_title: str,
        is_available: bool,
        confidence: float,
        matched_title: Optional[str] = None,
        matched_author: Optional[str] = None,
        reasoning: Optional[str] = None,
        recommended_keywords: Optional[List[str]] = None,
        error: Optional[str] = None
    ):
        self.book_title = book_title
        self.is_available = is_available
        self.confidence = confidence
        self.matched_title = matched_title
        self.matched_author = matched_author
        self.reasoning = reasoning
        self.recommended_keywords = recommended_keywords or []
        self.error = error

    def __repr__(self):
        return f"BookAnalysisResult(title={self.book_title}, available={self.is_available}, confidence={self.confidence})"


class LLMAnalyzer:
    """LLM分析器"""
    
    SYSTEM_PROMPT = """你是一个专业的图书信息分析助手。你的任务是根据微信读书的搜索结果，判断指定的书籍是否在微信读书平台**已上架且可阅读**。

**重要说明**：
- 微信读书有"已上架可阅读"和"待上架（可订阅但不可阅读）"两种状态
- 搜索结果中的每本书会标注 availability_status 字段，表示其状态
- **只有** availability_status 为"已上架可阅读"的书籍才算真正上架
- availability_status 为"待上架（可订阅但不可阅读）"的书籍**不算**上架

判断标准：
1. 书名是否匹配（允许中英文名、繁简体、版本差异）
2. 作者是否匹配（如果提供了作者信息）
3. **必须检查 availability_status 是否为"已上架可阅读"**
4. 如果找到匹配的书但状态是"待上架"，则判断为未上架
5. 如果搜索结果为空或没有找到匹配的书籍，则判断为未上架

请以JSON格式返回分析结果，包含以下字段：
- is_available: 布尔值，是否已上架且可阅读（待上架的书应该返回false）
- confidence: 浮点数（0-1），匹配置信度
- matched_title: 字符串，匹配到的书名（如果有）
- matched_author: 字符串，匹配到的作者（如果有）
- reasoning: 字符串，判断理由（如果是待上架，请明确说明）
- recommended_keywords: 字符串数组，推荐的搜索关键词（用于改进搜索）

示例1（已上架）：
{
    "is_available": true,
    "confidence": 0.95,
    "matched_title": "人类简史",
    "matched_author": "尤瓦尔·赫拉利",
    "reasoning": "找到完全匹配的书籍，书名和作者都一致，且状态为'已上架可阅读'",
    "recommended_keywords": ["人类简史", "Sapiens"]
}

示例2（待上架）：
{
    "is_available": false,
    "confidence": 0.95,
    "matched_title": "林登约翰逊传",
    "matched_author": "罗伯特·卡洛",
    "reasoning": "找到匹配的书籍，但状态为'待上架（可订阅但不可阅读）'，所以判断为未上架",
    "recommended_keywords": ["林登约翰逊传", "罗伯特卡洛"]
}
"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url
        )
    
    def _build_user_prompt(
        self,
        book_title: str,
        author: Optional[str],
        title_en: Optional[str],
        search_result: WeReadSearchResult
    ) -> str:
        """构建用户提示词"""
        prompt_parts = [
            f"目标书籍：{book_title}",
        ]
        
        if author:
            prompt_parts.append(f"作者：{author}")
        
        if title_en:
            prompt_parts.append(f"英文名：{title_en}")
        
        prompt_parts.append(f"\n使用的搜索关键词：{search_result.search_keyword}")
        
        if search_result.error:
            prompt_parts.append(f"\n搜索错误：{search_result.error}")
            prompt_parts.append("\n由于搜索出错，请判断为未上架。")
        elif search_result.found_books:
            prompt_parts.append(f"\n搜索结果（找到{len(search_result.found_books)}本书籍）：")
            for i, book in enumerate(search_result.found_books[:10], 1):
                prompt_parts.append(f"\n{i}. 书名：{book.get('title', 'N/A')}")
                if book.get('author'):
                    prompt_parts.append(f"   作者：{book.get('author', 'N/A')}")
                # 添加可读状态信息
                availability_status = book.get('availability_status', '未知')
                prompt_parts.append(f"   **状态：{availability_status}**")
        else:
            prompt_parts.append("\n搜索结果：未找到任何书籍")
        
        prompt_parts.append("\n\n请分析以上搜索结果，判断目标书籍是否在微信读书上架，并以JSON格式返回结果。")
        
        return "\n".join(prompt_parts)
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            # 尝试直接解析JSON
            result = json.loads(response_text)
            return result
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取JSON块
            logger.warning("LLM响应不是纯JSON，尝试提取JSON块")
            
            # 查找JSON代码块
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    pass
            
            # 查找大括号包围的内容
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                json_text = response_text[start:end]
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    pass
            
            # 解析失败，返回默认值
            logger.error(f"无法解析LLM响应: {response_text}")
            return {
                "is_available": False,
                "confidence": 0.0,
                "matched_title": None,
                "matched_author": None,
                "reasoning": "LLM响应解析失败",
                "recommended_keywords": []
            }
    
    def analyze_search_result(
        self,
        book_title: str,
        search_result: WeReadSearchResult,
        author: Optional[str] = None,
        max_retries: int = 3
    ) -> BookAnalysisResult:
        """
        分析搜索结果
        
        Args:
            book_title: 书名
            search_result: 搜索结果
            author: 作者
            max_retries: 最大重试次数
        
        Returns:
            分析结果
        """
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                logger.info(f"分析书籍搜索结果: {book_title} (尝试 {retry_count + 1}/{max_retries})")
                
                # 构建提示词
                user_prompt = self._build_user_prompt(book_title, author, None, search_result)
                
                # 调用LLM
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    response_format={"type": "json_object"}  # 要求返回JSON
                )
                
                # 获取响应文本
                response_text = response.choices[0].message.content
                logger.debug(f"LLM响应: {response_text}")
                
                # 解析响应
                parsed_result = self._parse_llm_response(response_text)
                
                # 构建分析结果
                return BookAnalysisResult(
                    book_title=book_title,
                    is_available=parsed_result.get("is_available", False),
                    confidence=parsed_result.get("confidence", 0.0),
                    matched_title=parsed_result.get("matched_title"),
                    matched_author=parsed_result.get("matched_author"),
                    reasoning=parsed_result.get("reasoning"),
                    recommended_keywords=parsed_result.get("recommended_keywords", [])
                )
                
            except (APIError, APIConnectionError, RateLimitError, APITimeoutError) as e:
                logger.error(f"LLM API错误: {e}")
                last_error = str(e)
                retry_count += 1
                
                if retry_count < max_retries:
                    logger.info(f"等待后重试...")
                    import time
                    time.sleep(2 ** retry_count)  # 指数退避
            
            except Exception as e:
                logger.error(f"分析过程出错: {e}")
                last_error = str(e)
                retry_count += 1
                
                if retry_count < max_retries:
                    import time
                    time.sleep(1)
        
        # 所有重试都失败
        logger.error(f"LLM分析失败，已达到最大重试次数: {book_title}")
        return BookAnalysisResult(
            book_title=book_title,
            is_available=False,
            confidence=0.0,
            reasoning=f"LLM分析失败: {last_error}",
            error=last_error
        )
    
    def batch_analyze(
        self,
        books: List[Dict[str, Any]],
        search_results: List[WeReadSearchResult]
    ) -> List[BookAnalysisResult]:
        """
        批量分析搜索结果
        
        Args:
            books: 书籍信息列表
            search_results: 搜索结果列表
        
        Returns:
            分析结果列表
        """
        if len(books) != len(search_results):
            raise ValueError("books和search_results长度必须相同")
        
        results = []
        for book, search_result in zip(books, search_results):
            result = self.analyze_search_result(
                book_title=book.get('title', ''),
                search_result=search_result,
                author=book.get('author'),
                title_en=book.get('title_en')
            )
            results.append(result)
        
        return results

