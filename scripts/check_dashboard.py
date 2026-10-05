import ast
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "dashboard.py"
ast.parse(source.read_text(encoding="utf-8"))
print("dashboard ok")
