#!/usr/bin/env python3
"""辅助工具：获取Notion数据库ID"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# 设置调试级别日志
logger.remove()
logger.add(sys.stdout, level="DEBUG", colorize=True)

from src.config import get_config
from src.notion_client import NotionBookClient


def main():
    """主函数"""
    print("=" * 60)
    print("Notion 数据库 ID 查询工具")
    print("=" * 60)
    print()
    
    try:
        # 加载配置
        config = get_config()
        
        print(f"Notion API Token (前10位): {config.notion.api_token[:10]}...")
        print(f"Database ID: {config.notion.database_id or '(未设置)'}")
        print()
        
        # 创建Notion客户端
        client = NotionBookClient(config.notion)
        
        print("正在查询可访问的数据库...")
        print()
        
        # 列出所有数据库
        databases = client.list_databases()
        
        if not databases:
            print("❌ 没有找到可访问的数据库")
            print()
            print("请检查：")
            print("1. Notion API Token 是否正确")
            print("2. Integration 是否已连接到数据库")
            return
        
        print(f"✅ 找到 {len(databases)} 个数据库：")
        print()
        
        for i, db in enumerate(databases, 1):
            # 提取标题
            title = ""
            if "title" in db:
                title_list = db.get("title", [])
                if title_list:
                    title = "".join([t.get("plain_text", "") for t in title_list])
            
            db_id = db.get("id", "")
            
            print(f"{i}. {title}")
            print(f"   ID: {db_id}")
            print()
        
        print("=" * 60)
        print("请将对应数据库的 ID 复制到配置文件中")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

