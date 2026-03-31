"""
Output module – currently writes results to a JSON file.
Swap this module later to write into the database or another sink.
"""

import json
import os
from datetime import datetime


def write_json(data: dict, output_dir: str = ".") -> str:
    """
    Serialize *data* to a timestamped JSON file inside *output_dir*.
    Returns the path to the written file.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"production_bugs_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)

    print(f"Output written to: {filepath}")
    return filepath
