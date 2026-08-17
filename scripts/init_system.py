"""一键初始化入口：python scripts/init_system.py（FR-INIT）。"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from backend.utils.seed import init_system

if __name__ == "__main__":
    print(init_system())
