import json
from pathlib import Path

from chase201.main import app

Path("openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
