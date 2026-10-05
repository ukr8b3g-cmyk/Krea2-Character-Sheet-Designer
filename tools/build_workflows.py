"""Read the sole user-supplied template without generating alternative workflows.

The canonical JSON is maintained directly and is byte-identical to the supplied
file. Running this historical entry point validates it; it never rewrites it.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'workflows/Krea2_Layout_Reference_Designer.json'
TEMPLATE_SHA256 = 'cd15879da50979467637eeae41dc5d94cec099b4cb5bfdf4a02f925f40ba8e14'


def build():
    """Return a fresh in-memory copy of the canonical saved GUI workflow."""
    return json.loads(TEMPLATE.read_text(encoding='utf-8'))


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    from tools.validate_workflows import run
    print(json.dumps(run(), indent=2))
