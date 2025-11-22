#!/usr/bin/env python3
"""手动运行脚本"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.main import main

if __name__ == "__main__":
    print("=" * 60)
    print("Book Finder - 手动运行模式")
    print("=" * 60)
    print()
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n任务已被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n任务执行失败: {e}")
        sys.exit(1)

