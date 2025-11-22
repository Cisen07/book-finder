#!/usr/bin/env python3
"""检查Notion数据库结构"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True)

from src.config import get_config
from src.notion_client import NotionBookClient


def main():
    print("=" * 60)
    print("Notion 数据库结构检查")
    print("=" * 60)
    print()
    
    try:
        config = get_config()
        client = NotionBookClient(config.notion)
        
        print(f"数据库 ID: {config.notion.database_id}")
        print()
        
        # 获取数据库信息
        db_info = client.client.data_sources.retrieve(data_source_id=config.notion.database_id)
        
        print("数据库标题:")
        title_list = db_info.get("title", [])
        if title_list:
            title = "".join([t.get("plain_text", "") for t in title_list])
            print(f"  {title}")
        print()
        
        print("当前列（Properties）：")
        print("-" * 60)
        
        properties = db_info.get("properties", {})
        
        if not properties:
            print("⚠️  数据库没有任何列！")
        else:
            for prop_name, prop_info in properties.items():
                prop_type = prop_info.get("type", "unknown")
                prop_id = prop_info.get("id", "")
                print(f"• {prop_name}")
                print(f"  类型: {prop_type}")
                print(f"  ID: {prop_id}")
                print()
        
        print("=" * 60)
        print("需要的列配置（用于本项目）：")
        print("=" * 60)
        print()
        
        required_props = [
            ("书名/Name", "title", "必需", "书籍的主要标识"),
            ("作者/Author", "rich_text", "推荐", "提高搜索准确度"),
            ("英文名/English Name", "rich_text", "推荐", "英文书籍搜索"),
            ("ISBN", "rich_text", "可选", "备用搜索关键词"),
            ("状态/Status", "select", "可选", "如：想读、在读、已读"),
            ("已上架/Available", "checkbox", "自动", "程序自动更新"),
            ("最后检查时间/Last Check", "date", "自动", "程序自动更新"),
            ("搜索关键词/Keywords", "rich_text", "自动", "程序自动更新"),
        ]
        
        for name, prop_type, importance, desc in required_props:
            marker = "✅" if importance == "必需" else "📌" if importance == "推荐" else "🔄" if importance == "自动" else "📝"
            print(f"{marker} {name}")
            print(f"   类型: {prop_type}")
            print(f"   重要性: {importance}")
            print(f"   说明: {desc}")
            print()
        
        print("=" * 60)
        print("提示：")
        print("1. 如果缺少列，可以运行 'python tools/init_database.py' 自动初始化")
        print("2. 或者手动在 Notion 中添加上述列")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

