"""
Output module – writes collector results to a timestamped JSON file.
"""

import json
import os
from datetime import datetime


def write_json(data: dict, output_dir: str = ".", prefix: str = "gitlab_tags") -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)

    print(f"Output written to: {filepath}")
    return filepath
