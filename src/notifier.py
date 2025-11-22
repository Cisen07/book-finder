"""通知模块"""

from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from loguru import logger

from .config import NotificationConfig


class NotificationMessage:
    """通知消息"""
    
    def __init__(
        self,
        total_books: int,
        available_books: int,
        unavailable_books: int,
        newly_available: List[Dict[str, str]],
        failed_books: List[Dict[str, str]],
        check_time: Optional[datetime] = None
    ):
        self.total_books = total_books
        self.available_books = available_books
        self.unavailable_books = unavailable_books
        self.newly_available = newly_available
        self.failed_books = failed_books
        self.check_time = check_time or datetime.now()


class Notifier:
    """通知发送器"""
    
    def __init__(self, config: NotificationConfig):
        self.config = config
    
    def _build_wecom_message(self, message: NotificationMessage) -> Dict[str, Any]:
        """构建企业微信消息"""
        # 构建Markdown格式消息
        lines = [
            f"## 📚 书籍检查报告",
            f"",
            f"**检查时间**: {message.check_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"### 📊 统计信息",
            f"- 总书籍数: {message.total_books}",
            f"- 已上架: {message.available_books} 本",
            f"- 未上架: {message.unavailable_books} 本",
        ]
        
        # 新上架书籍
        if message.newly_available:
            lines.append(f"")
            lines.append(f"### ✅ 新上架书籍 ({len(message.newly_available)})")
            for book in message.newly_available[:10]:  # 最多显示10本
                title = book.get('title', '未知')
                author = book.get('author', '')
                if author:
                    lines.append(f"- **{title}** - {author}")
                else:
                    lines.append(f"- **{title}**")
        
        # 检查失败的书籍
        if message.failed_books:
            lines.append(f"")
            lines.append(f"### ⚠️ 检查失败 ({len(message.failed_books)})")
            for book in message.failed_books[:5]:  # 最多显示5本
                title = book.get('title', '未知')
                error = book.get('error', '未知错误')
                lines.append(f"- {title}: {error}")
        
        markdown_content = "\n".join(lines)
        
        return {
            "msgtype": "markdown",
            "markdown": {
                "content": markdown_content
            }
        }
    
    def _build_feishu_message(self, message: NotificationMessage) -> Dict[str, Any]:
        """构建飞书消息"""
        # 构建卡片内容
        card_elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**检查时间**: {message.check_time.strftime('%Y-%m-%d %H:%M:%S')}"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**📊 统计信息**\n总书籍数: {message.total_books}\n已上架: {message.available_books} 本\n未上架: {message.unavailable_books} 本"
                }
            }
        ]
        
        # 新上架书籍
        if message.newly_available:
            card_elements.append({"tag": "hr"})
            newly_available_content = f"**✅ 新上架书籍 ({len(message.newly_available)})**\n"
            for book in message.newly_available[:10]:
                title = book.get('title', '未知')
                author = book.get('author', '')
                if author:
                    newly_available_content += f"• {title} - {author}\n"
                else:
                    newly_available_content += f"• {title}\n"
            
            card_elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": newly_available_content.strip()
                }
            })
        
        # 检查失败的书籍
        if message.failed_books:
            card_elements.append({"tag": "hr"})
            failed_content = f"**⚠️ 检查失败 ({len(message.failed_books)})**\n"
            for book in message.failed_books[:5]:
                title = book.get('title', '未知')
                error = book.get('error', '未知错误')
                failed_content += f"• {title}: {error}\n"
            
            card_elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": failed_content.strip()
                }
            })
        
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📚 书籍检查报告"
                    },
                    "template": "blue"
                },
                "elements": card_elements
            }
        }
    
    def send_wecom(self, message: NotificationMessage) -> bool:
        """发送企业微信通知"""
        if not self.config.wecom_webhook:
            logger.warning("企业微信Webhook未配置，跳过发送")
            return False
        
        try:
            logger.info("发送企业微信通知")
            
            payload = self._build_wecom_message(message)
            
            response = requests.post(
                self.config.wecom_webhook,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    logger.info("企业微信通知发送成功")
                    return True
                else:
                    logger.error(f"企业微信通知发送失败: {result}")
                    return False
            else:
                logger.error(f"企业微信通知发送失败: HTTP {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"发送企业微信通知异常: {e}")
            return False
    
    def send_feishu(self, message: NotificationMessage) -> bool:
        """发送飞书通知"""
        if not self.config.feishu_webhook:
            logger.warning("飞书Webhook未配置，跳过发送")
            return False
        
        try:
            logger.info("发送飞书通知")
            
            payload = self._build_feishu_message(message)
            
            response = requests.post(
                self.config.feishu_webhook,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0 or result.get("StatusCode") == 0:
                    logger.info("飞书通知发送成功")
                    return True
                else:
                    logger.error(f"飞书通知发送失败: {result}")
                    return False
            else:
                logger.error(f"飞书通知发送失败: HTTP {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"发送飞书通知异常: {e}")
            return False
    
    def send(self, message: NotificationMessage) -> Dict[str, bool]:
        """
        发送通知到所有启用的渠道
        
        Args:
            message: 通知消息
        
        Returns:
            各渠道发送结果
        """
        results = {}
        
        enabled_channels = self.config.enabled_channels or []
        
        # 发送企业微信通知
        if "wecom" in enabled_channels:
            results["wecom"] = self.send_wecom(message)
        
        # 发送飞书通知
        if "feishu" in enabled_channels:
            results["feishu"] = self.send_feishu(message)
        
        # 统计成功数量
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        logger.info(f"通知发送完成: {success_count}/{total_count} 成功")
        
        return results

