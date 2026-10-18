from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def convert(src: str, dest: str, export_name: str, old_fn: str) -> None:
    text = (ROOT / src).read_text(encoding="utf-8")
    text = text.replace(
        'import { createFileRoute, Link } from "@tanstack/react-router";',
        'import { Link } from "react-router-dom";',
    )
    text = re.sub(
        r"export const Route = createFileRoute\([^\)]+\)\(\{.*?\n\}\);\n\n",
        "",
        text,
        count=1,
        flags=re.S,
    )
    text = text.replace(f"function {old_fn}()", f"export function {export_name}()")
    out = ROOT / dest
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(dest, "has_Route=", "export const Route" in text)


convert("frontend/src/routes/index.tsx", "frontend/src/pages/HomePage.tsx", "HomePage", "Home")
convert("frontend/src/routes/auth.tsx", "frontend/src/pages/AuthPage.tsx", "AuthPage", "AuthPage")
