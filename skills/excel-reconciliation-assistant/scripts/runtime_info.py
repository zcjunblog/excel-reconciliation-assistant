"""Version relative to the installed skill, independent of cwd and host paths."""
from pathlib import Path
import re


def skill_version(base=None):
    root=Path(base) if base is not None else Path(__file__).resolve().parents[1]
    try: value=(root/'VERSION').read_text(encoding='utf-8').strip()
    except OSError as error: raise ValueError('Skill VERSION is missing or unreadable') from error
    if len(value)>64 or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',value):
        raise ValueError('Skill VERSION must be a semantic version')
    return value
