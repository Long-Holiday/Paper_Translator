import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，便于直接测试导入
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
