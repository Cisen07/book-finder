"""配置管理模块"""

import os
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotionConfig(BaseSettings):
    """Notion配置"""
    api_token: str = Field(description="Notion API Token")
    database_id: str = Field(description="Database ID")

    model_config = SettingsConfigDict(env_prefix="NOTION_")


class LLMConfig(BaseSettings):
    """LLM配置"""
    base_url: str = Field(default="https://cloud.infini-ai.com/maas")
    api_key: str = Field(description="LLM API Key")
    model: str = Field(default="claude-sonnet-4-5-20250929")
    temperature: float = Field(default=0.3)
    max_tokens: int = Field(default=2000)

    model_config = SettingsConfigDict(env_prefix="LLM_")


class CrawlerConfig(BaseSettings):
    """爬虫配置"""
    headless: bool = Field(default=True)
    timeout: int = Field(default=30000)
    max_retries: int = Field(default=3)
    delay_min: float = Field(default=1.0)
    delay_max: float = Field(default=3.0)

    model_config = SettingsConfigDict(env_prefix="CRAWLER_")


class NotificationConfig(BaseSettings):
    """通知配置"""
    wecom_webhook: Optional[str] = Field(default=None)
    feishu_webhook: Optional[str] = Field(default=None)
    enabled_channels: List[str] = Field(default_factory=lambda: ["wecom", "feishu"])

    model_config = SettingsConfigDict(env_prefix="NOTIFICATION_")


class SchedulerConfig(BaseSettings):
    """调度配置"""
    enabled: bool = Field(default=True)
    cron: str = Field(default="0 9 * * *")
    timezone: str = Field(default="Asia/Shanghai")

    model_config = SettingsConfigDict(env_prefix="SCHEDULER_")


class LoggingConfig(BaseSettings):
    """日志配置"""
    level: str = Field(default="INFO")
    format: str = Field(
        default="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    )
    rotation: str = Field(default="10 MB")
    retention: str = Field(default="30 days")

    model_config = SettingsConfigDict(env_prefix="LOGGING_")


class Config(BaseSettings):
    """主配置类"""
    notion: NotionConfig = Field(default_factory=NotionConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore"
    )

    @classmethod
    def load_from_yaml(cls, yaml_path: str = "config/config.yaml") -> "Config":
        """从YAML文件加载配置"""
        yaml_file = Path(yaml_path)
        if yaml_file.exists():
            with open(yaml_file, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}
            
            # 创建各个子配置
            notion_config = NotionConfig(**yaml_data.get("notion", {}))
            llm_config = LLMConfig(**yaml_data.get("llm", {}))
            crawler_config = CrawlerConfig(**yaml_data.get("crawler", {}))
            notification_config = NotificationConfig(**yaml_data.get("notification", {}))
            scheduler_config = SchedulerConfig(**yaml_data.get("scheduler", {}))
            logging_config = LoggingConfig(**yaml_data.get("logging", {}))
            
            return cls(
                notion=notion_config,
                llm=llm_config,
                crawler=crawler_config,
                notification=notification_config,
                scheduler=scheduler_config,
                logging=logging_config
            )
        else:
            # 如果YAML文件不存在，从环境变量加载
            return cls()

    @classmethod
    def load(cls) -> "Config":
        """智能加载配置：优先从YAML加载，然后环境变量覆盖"""
        # 尝试从YAML加载
        config_paths = [
            "config/config.yaml",
            "config.yaml",
            "/app/config/config.yaml"
        ]
        
        for path in config_paths:
            if Path(path).exists():
                return cls.load_from_yaml(path)
        
        # 如果没有YAML文件，从环境变量加载
        return cls(
            notion=NotionConfig(),
            llm=LLMConfig(),
            crawler=CrawlerConfig(),
            notification=NotificationConfig(),
            scheduler=SchedulerConfig(),
            logging=LoggingConfig()
        )


# 全局配置实例
_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config():
    """重新加载配置"""
    global _config
    _config = Config.load()
    return _config

