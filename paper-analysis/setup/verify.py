# -*- coding: utf-8 -*-
"""自检：确认技能依赖都能导入。
用法：<技能目录>/.venv/Scripts/python.exe setup/verify.py
"""
import sys

CHECKS = [
    ("openpyxl", "Excel 读写"),
    ("markitdown", "PDF -> Markdown"),
]

failed = []
for mod, desc in CHECKS:
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "")
        print(f"OK   {mod:<12} {desc} {ver}".rstrip())
    except Exception as e:
        failed.append(mod)
        print(f"FAIL {mod:<12} {desc}: {e}")

if failed:
    print(f"\n缺失 {len(failed)} 项，请先运行 setup/install.ps1 或 setup/install.sh")
    sys.exit(1)
print("\n全部依赖就绪。")
