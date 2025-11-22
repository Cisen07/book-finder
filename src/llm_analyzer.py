"""LLM分析模块"""

import json
from typing import Dict, Any, Optional, List

from loguru import logger
from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError

from .config import LLMConfig
from .weread_api import WeReadSearchResult


class SearchKeywordsResult:
    """搜索关键词生成结果"""
    
    def __init__(
        self,
        book_title: str,
        keywords: List[str],
        corrected_title: Optional[str] = None,
        corrected_author: Optional[str] = None,
        reasoning: Optional[str] = None,
        error: Optional[str] = None
    ):
        self.book_title = book_title
        self.keywords = keywords
        self.corrected_title = corrected_title
        self.corrected_author = corrected_author
        self.reasoning = reasoning
        self.error = error
    
    def __repr__(self):
        return f"SearchKeywordsResult(title={self.book_title}, keywords={self.keywords})"


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


class SearchKeywordsResult:
    """搜索关键词生成结果"""
    
    def __init__(
        self,
        book_title: str,
        keywords: List[str],
        corrected_title: Optional[str] = None,
        corrected_author: Optional[str] = None,
        reasoning: Optional[str] = None,
        error: Optional[str] = None
    ):
        self.book_title = book_title
        self.keywords = keywords
        self.corrected_title = corrected_title
        self.corrected_author = corrected_author
        self.reasoning = reasoning
        self.error = error


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

**特别说明 - 中英文版本匹配**：
- 如果目标书籍是英文原版（如 "Sapiens"），找到对应的中文译本（如 "人类简史"）**也算已上架**
- 如果目标书籍是中文版，找到英文原版也可以算已上架，但优先匹配中文版
- 判断是否为同一本书的依据：作者一致、内容主题一致、是否为翻译版本
- 在 reasoning 中需要明确说明找到的是原版还是译本

**不确定情况的处理**：
- 如果匹配度较低（confidence < 0.7），在 reasoning 中详细说明不确定的原因，方便人工复核
- 如果有多个候选结果但难以判断，列出所有可能的选项供人工确认
- 如果只是书名相似但作者不一致，需要在 reasoning 中特别说明

请以JSON格式返回分析结果，包含以下字段：
- is_available: 布尔值，是否已上架且可阅读（待上架的书应该返回false）
- confidence: 浮点数（0-1），匹配置信度
- matched_title: 字符串，匹配到的书名（如果有）
- matched_author: 字符串，匹配到的作者（如果有）
- reasoning: 字符串，判断理由。**特别注意**：如果不确定、有多个候选、或需要人工复核，请在此详细说明
- recommended_keywords: 字符串数组，推荐的搜索关键词（用于改进搜索）

示例1（已上架 - 完全匹配）：
{
    "is_available": true,
    "confidence": 0.95,
    "matched_title": "人类简史",
    "matched_author": "尤瓦尔·赫拉利",
    "reasoning": "找到完全匹配的书籍，书名和作者都一致，且状态为'已上架可阅读'",
    "recommended_keywords": ["人类简史", "Sapiens"]
}

示例2（已上架 - 找到中文译本）：
{
    "is_available": true,
    "confidence": 0.90,
    "matched_title": "人类简史：从动物到上帝",
    "matched_author": "尤瓦尔·赫拉利",
    "reasoning": "目标书籍是英文原版 'Sapiens'，找到了对应的中文译本《人类简史：从动物到上帝》，作者一致，内容相同，状态为'已上架可阅读'，判断为已上架",
    "recommended_keywords": ["Sapiens", "人类简史", "尤瓦尔赫拉利"]
}

示例3（待上架）：
{
    "is_available": false,
    "confidence": 0.95,
    "matched_title": "林登约翰逊传",
    "matched_author": "罗伯特·卡洛",
    "reasoning": "找到匹配的书籍，但状态为'待上架（可订阅但不可阅读）'，所以判断为未上架",
    "recommended_keywords": ["林登约翰逊传", "罗伯特卡洛"]
}

示例4（不确定 - 需要人工复核）：
{
    "is_available": false,
    "confidence": 0.60,
    "matched_title": null,
    "matched_author": null,
    "reasoning": "搜索结果中有2本书名相似的书籍：1)《经济学原理》(曼昆) 已上架；2)《经济学原理》(萨缪尔森) 已上架。目标书籍未明确作者，无法准确判断是哪一本。建议人工复核或补充作者信息后重新搜索",
    "recommended_keywords": ["经济学原理 曼昆", "经济学原理 萨缪尔森"]
}
"""
    
    SEARCH_KEYWORDS_SYSTEM_PROMPT = """你是一个专业的图书搜索助手。你的任务是根据用户提供的书名和作者信息，生成最优的搜索关键词列表，用于在微信读书平台搜索书籍。

你需要考虑：
1. 可能的错别字或拼写错误
2. 书名的不同表述方式（简称、全称、副标题等）
3. 作者名字的不同写法（中文、英文、简称、全称等）
4. 关键词组合的多样性（书名单独、书名+作者、关键词等）

**特别重要 - 中英文版本**：
5. 如果书名是**英文**，需要：
   - 生成可能的中文译名（常见译名、直译等）
   - 同时保留英文原名作为搜索关键词
   - 优先使用中文译名，因为微信读书上中文译本更常见
   
6. 如果书名是**中文**，但可能是翻译作品：
   - 尝试推测可能的英文原名
   - 生成中英文组合的搜索关键词

**示例说明**：
- 如果书名是 "Sapiens"，应生成：["人类简史", "Sapiens", "人类简史 尤瓦尔", "智人", ...]
- 如果书名是 "The Great Gatsby"，应生成：["了不起的盖茨比", "伟大的盖茨比", "The Great Gatsby", "盖茨比", ...]
- 如果书名是 "Thinking, Fast and Slow"，应生成：["思考快与慢", "思考，快与慢", "快思慢想", "Thinking Fast and Slow", ...]

请生成3-5个最有可能找到该书籍的搜索关键词，按优先级排序（中文译名优先）。"""
    
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
                
                # 记录LLM请求参数
                logger.info("=" * 60)
                logger.info("LLM分析请求参数:")
                logger.info(f"  模型: {self.config.model}")
                logger.info(f"  温度: {self.config.temperature}")
                logger.info(f"  最大tokens: {self.config.max_tokens}")
                logger.info(f"System Prompt (前200字): {self.SYSTEM_PROMPT[:200]}...")
                logger.info(f"User Prompt:\n{user_prompt}")
                logger.info("=" * 60)
                
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
                
                # 记录完整的LLM响应
                logger.info("=" * 60)
                logger.info("LLM分析响应:")
                logger.info(f"  模型: {response.model}")
                logger.info(f"  完成原因: {response.choices[0].finish_reason}")
                logger.info(f"  用量统计: prompt_tokens={response.usage.prompt_tokens}, completion_tokens={response.usage.completion_tokens}, total_tokens={response.usage.total_tokens}")
                logger.info(f"响应内容:\n{response_text}")
                logger.info("=" * 60)
                
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
                author=book.get('author')
            )
            results.append(result)
        
        return results
    
    def generate_search_keywords(
        self,
        book_title: str,
        author: Optional[str] = None,
        max_retries: int = 3
    ) -> 'SearchKeywordsResult':
        """
        使用LLM生成优化的搜索关键词
        
        Args:
            book_title: 书名
            author: 作者
            max_retries: 最大重试次数
        
        Returns:
            搜索关键词结果
        """
        logger.info(f"生成搜索关键词: {book_title} (作者: {author or '未知'})")
        
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                if retry_count > 0:
                    logger.info(f"重试生成搜索关键词 (尝试 {retry_count + 1}/{max_retries})")
                
                # 构建提示词
                user_prompt = self._build_keywords_prompt(book_title, author)
                
                # 记录LLM请求参数
                logger.info("=" * 60)
                logger.info("LLM关键词生成请求参数:")
                logger.info(f"  模型: {self.config.model}")
                logger.info(f"  温度: {self.config.temperature}")
                logger.info(f"  最大tokens: 1000")
                logger.info(f"System Prompt (前200字): {self.SEARCH_KEYWORDS_SYSTEM_PROMPT[:200]}...")
                logger.info(f"User Prompt:\n{user_prompt}")
                logger.info("=" * 60)
                
                # 调用LLM
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": self.SEARCH_KEYWORDS_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.config.temperature,
                    max_tokens=1000
                )
                
                # 解析响应
                result_text = response.choices[0].message.content.strip()
                
                # 记录完整的LLM响应
                logger.info("=" * 60)
                logger.info("LLM关键词生成响应:")
                logger.info(f"  模型: {response.model}")
                logger.info(f"  完成原因: {response.choices[0].finish_reason}")
                logger.info(f"  用量统计: prompt_tokens={response.usage.prompt_tokens}, completion_tokens={response.usage.completion_tokens}, total_tokens={response.usage.total_tokens}")
                logger.info(f"响应内容:\n{result_text}")
                logger.info("=" * 60)
                
                # 解析JSON结果
                result = self._parse_keywords_response(result_text, book_title)
                
                logger.info(f"✓ 成功生成 {len(result.keywords)} 个搜索关键词")
                if result.corrected_title and result.corrected_title != book_title:
                    logger.info(f"  书名纠正: {book_title} → {result.corrected_title}")
                if result.corrected_author and result.corrected_author != author:
                    logger.info(f"  作者纠正: {author} → {result.corrected_author}")
                for i, kw in enumerate(result.keywords[:3], 1):
                    logger.info(f"  关键词{i}: {kw}")
                
                return result
            
            except (APIError, APIConnectionError, RateLimitError, APITimeoutError) as e:
                logger.error(f"LLM API错误: {e}")
                last_error = str(e)
                retry_count += 1
                
                if retry_count < max_retries:
                    import time
                    time.sleep(2 ** retry_count)
            
            except Exception as e:
                logger.error(f"生成关键词失败: {e}")
                last_error = str(e)
                retry_count += 1
                
                if retry_count < max_retries:
                    import time
                    time.sleep(1)
        
        # 所有重试都失败，返回默认关键词
        logger.warning(f"LLM生成关键词失败，使用默认关键词")
        default_keywords = [book_title]
        if author:
            default_keywords.append(f"{book_title} {author}")
        
        return SearchKeywordsResult(
            book_title=book_title,
            keywords=default_keywords,
            error=f"LLM生成失败，使用默认关键词: {last_error}"
        )
    
    def _build_keywords_prompt(self, book_title: str, author: Optional[str] = None) -> str:
        """构建关键词生成提示词"""
        prompt = f"""请为以下书籍生成最优的搜索关键词列表：

书名：{book_title}"""
        
        if author:
            prompt += f"\n作者：{author}"
        
        prompt += """

请分析书名和作者信息，考虑可能的错别字、不同表述方式，生成3-5个最优搜索关键词。

**特别注意**：
- 如果书名是英文，请优先生成可能的中文译名作为搜索关键词（因为微信读书上中文译本更常见）
- 同时保留英文原名作为备选关键词
- 中文译名应该放在关键词列表的前面（优先级更高）

请返回JSON格式的结果，包含以下字段：
- corrected_title: 纠正后的书名（如果原书名有错别字或不规范的地方，否则与原书名相同）
- corrected_author: 纠正后的作者名（如果有，否则null）
- keywords: 搜索关键词列表（3-5个，按优先级从高到低排序，英文书名时中文译名优先）
- reasoning: 生成这些关键词的理由（简短说明）

示例1（中文书名）：
```json
{
  "corrected_title": "人类简史：从动物到上帝",
  "corrected_author": "尤瓦尔·赫拉利",
  "keywords": [
    "人类简史",
    "人类简史 尤瓦尔·赫拉利",
    "Sapiens",
    "从动物到上帝",
    "人类简史 赫拉利"
  ],
  "reasoning": "使用书名全称和简称，结合作者名的不同写法，及英文原名增加搜索覆盖"
}
```

示例2（英文书名 - 重点）：
```json
{
  "corrected_title": "Sapiens",
  "corrected_author": "Yuval Noah Harari",
  "keywords": [
    "人类简史",
    "智人",
    "Sapiens",
    "人类简史 尤瓦尔",
    "从动物到上帝"
  ],
  "reasoning": "英文书名'Sapiens'，生成常见中文译名'人类简史'和'智人'作为优先搜索词，因为微信读书上中文译本更常见。保留英文原名作为备选"
}
```

示例3（可能有错别字）：
```json
{
  "corrected_title": "林登·约翰逊传",
  "corrected_author": "罗伯特·卡罗",
  "keywords": [
    "林登约翰逊传",
    "林登·约翰逊传",
    "约翰逊传记",
    "罗伯特卡罗 约翰逊",
    "LBJ传"
  ],
  "reasoning": "使用有无间隔号的不同写法，简称LBJ，结合作者名"
}
```

示例4（英文书名且较长）：
```json
{
  "corrected_title": "Thinking, Fast and Slow",
  "corrected_author": "Daniel Kahneman",
  "keywords": [
    "思考快与慢",
    "思考，快与慢",
    "快思慢想",
    "Thinking Fast and Slow",
    "卡尼曼"
  ],
  "reasoning": "英文书名，生成多个常见中文译名版本（有无标点差异），保留英文原名，添加作者中文名作为备选"
}
```

请直接返回JSON，不要包含其他文字。"""
        
        return prompt
    
    def _parse_keywords_response(self, response_text: str, book_title: str) -> 'SearchKeywordsResult':
        """解析LLM的关键词生成响应"""
        try:
            # 尝试直接解析JSON
            result_dict = self._parse_llm_response(response_text)
            
            # 提取字段
            keywords = result_dict.get("keywords", [])
            if not keywords or not isinstance(keywords, list):
                # 如果没有关键词或格式不对，使用原书名
                keywords = [book_title]
            
            corrected_title = result_dict.get("corrected_title")
            corrected_author = result_dict.get("corrected_author")
            reasoning = result_dict.get("reasoning")
            
            return SearchKeywordsResult(
                book_title=book_title,
                keywords=keywords,
                corrected_title=corrected_title,
                corrected_author=corrected_author,
                reasoning=reasoning
            )
        
        except Exception as e:
            logger.error(f"解析关键词响应失败: {e}")
            # 返回默认关键词
            return SearchKeywordsResult(
                book_title=book_title,
                keywords=[book_title],
                error=f"解析失败: {str(e)}"
            )

