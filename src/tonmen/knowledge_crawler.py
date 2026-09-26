from __future__ import annotations

import json
import os

from tonmen.core.config import TonmenConfig
from tonmen.knowledge.crawler import run_for_workspace


def main() -> int:
    config_value = os.getenv("TONMEN_CONFIG", "").strip()
    config = TonmenConfig.default(config_value or None)
    result = run_for_workspace(config.workspace)
    print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
