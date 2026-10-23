from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = BACKEND_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from drivers.runtime import DriverHost, create_adapter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--driver", choices=("ros1", "ros2", "serial_json", "simulator"), required=True
    )
    arguments = parser.parse_args()
    host = DriverHost(arguments.driver)
    host.adapter = create_adapter(arguments.driver, host)
    return host.run()


if __name__ == "__main__":
    raise SystemExit(main())
