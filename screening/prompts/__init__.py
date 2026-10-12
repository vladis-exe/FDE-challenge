"""Prompt templates live as readable Markdown files in this directory.

Each file opens with an HTML comment saying what the prompt is for. The comment
is for people and is stripped before the text is sent to the model.
"""

import re
from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
_HEADER = re.compile(r"\A\s*<!--.*?-->\s*", re.S)


@cache
def load_prompt(name: str) -> str:
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return _HEADER.sub("", text).strip()
