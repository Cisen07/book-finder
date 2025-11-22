#!/usr/bin/env python3
"""初始化Notion数据库 - 添加所需的列"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True)

from src.config import get_config


def main():
    print("=" * 60)
    print("Notion 数据库初始化")
    print("=" * 60)
    print()
    
    try:
        config = get_config()
        
        from notion_client import Client
        client = Client(auth=config.notion.api_token)
        
        database_id = config.notion.database_id
        
        print(f"数据库 ID: {database_id}")
        print()
        
        # 获取当前数据库结构
        db_info = client.data_sources.retrieve(data_source_id=database_id)
        
        current_properties = db_info.get("properties", {})
        current_prop_names = set(current_properties.keys())
        
        print("当前已有的列：")
        for name in sorted(current_prop_names):
            prop_type = current_properties[name].get("type")
            print(f"  ✓ {name} ({prop_type})")
        print()
        
        # 定义需要添加的列
        # 格式：(列名, 列类型, 配置)
        properties_to_add = []
        
        # 作者
        if "作者" not in current_prop_names and "Author" not in current_prop_names:
            properties_to_add.append(("作者", "rich_text", {}))
        
        # ISBN
        if "ISBN" not in current_prop_names:
            properties_to_add.append(("ISBN", "rich_text", {}))
        
        # 状态
        if "状态" not in current_prop_names and "Status" not in current_prop_names:
            properties_to_add.append(("状态", "select", {
                "options": [
                    {"name": "想读", "color": "blue"},
                    {"name": "在读", "color": "yellow"},
                    {"name": "已读", "color": "green"},
                ]
            }))
        
        # 已上架
        if "已上架" not in current_prop_names and "Available" not in current_prop_names:
            properties_to_add.append(("已上架", "checkbox", {}))
        
        # 最后检查时间
        if "最后检查时间" not in current_prop_names and "Last Check" not in current_prop_names:
            properties_to_add.append(("最后检查时间", "date", {}))
        
        # 搜索关键词
        if "搜索关键词" not in current_prop_names and "Keywords" not in current_prop_names:
            properties_to_add.append(("搜索关键词", "rich_text", {}))
        
        # 备注
        if "备注" not in current_prop_names and "Notes" not in current_prop_names and "说明" not in current_prop_names:
            properties_to_add.append(("备注", "rich_text", {}))
        
        if not properties_to_add:
            print("✅ 数据库已包含所有必要的列，无需初始化")
            print()
            return
        
        print(f"需要添加 {len(properties_to_add)} 个列：")
        for name, prop_type, _ in properties_to_add:
            print(f"  • {name} ({prop_type})")
        print()
        
        # 询问用户确认
        response = input("是否继续添加这些列？(y/n): ").strip().lower()
        if response != 'y':
            print("❌ 已取消")
            return
        
        print()
        print("开始添加列...")
        print()
        
        # 构建更新的properties
        new_properties = {}
        
        for name, prop_type, config in properties_to_add:
            print(f"  添加: {name} ({prop_type})...")
            
            if prop_type == "rich_text":
                new_properties[name] = {"rich_text": {}}
            elif prop_type == "checkbox":
                new_properties[name] = {"checkbox": {}}
            elif prop_type == "date":
                new_properties[name] = {"date": {}}
            elif prop_type == "select":
                new_properties[name] = {"select": config}
            
            # 逐个添加（避免一次性更新可能的问题）
            try:
                client.data_sources.update(
                    data_source_id=database_id,
                    properties={name: new_properties[name]}
                )
                print(f"    ✓ 成功")
            except Exception as e:
                print(f"    ✗ 失败: {e}")
        
        print()
        print("=" * 60)
        print("✅ 数据库初始化完成！")
        print("=" * 60)
        print()
        print("现在可以：")
        print("1. 在 Notion 中添加书籍数据")
        print("2. 运行 'python run.py' 开始检查书籍")
        print()
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

