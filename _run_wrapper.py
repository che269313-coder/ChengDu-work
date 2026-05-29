#!/usr/bin/env python3
"""包装运行 update_html.py 并记录完整输出"""
import sys
import traceback

sys.path.insert(0, ".")

try:
    from scripts.update_html import main
    main()
    print("SUCCESS", flush=True)
except SystemExit as e:
    print(f"SystemExit: {e}", flush=True)
except Exception as e:
    traceback.print_exc()
    print(f"FAILED: {e}", flush=True)
    sys.exit(1)
