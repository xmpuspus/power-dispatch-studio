"""Render the README's 39-view deep-link table straight out of nav.ts.

Every studio view is addressable as `#v=<slug>`, so the README can carry all 39
for the price of some text rather than 39 embedded clips. GitHub applies no
lazy loading, so those clips would be about 200 MB fetched on open.

nav.ts is the only place the slug, the label and the one-line hint are written
down, so the table is generated from it and pinned by tests/test_readme_views.py.
Hand-editing a row is what this exists to prevent.

    python3 build/gen_view_table.py            # print the block
    python3 build/gen_view_table.py --write    # replace it in README.md
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAV = ROOT / "studio" / "src" / "shell" / "nav.ts"
README = ROOT / "README.md"
LIVE = "https://power-dispatch-studio.vercel.app/studio/"
START = "<!-- views:start -->"
END = "<!-- views:end -->"


def destinations() -> list[dict]:
    """slug, label, hint and question group, in the order nav.ts declares them."""
    src = NAV.read_text()
    body = src[src.index("export const GROUPS"):src.index("export const ALL_DESTS")]
    out: list[dict] = []
    group = ""
    pending: dict | None = None
    for m in re.finditer(
        r"slug:\s*'([^']+)'|label:\s*(?:'([^']*)'|\"([^\"]*)\")|hint:\s*(?:'([^']*)'|\"([^\"]*)\")",
        body,
    ):
        slug, lab, lab2, hint, hint2 = m.groups()
        if slug:
            pending = {"slug": slug, "group": group}
            out.append(pending)
        elif lab or lab2:
            if pending and "label" not in pending:
                pending["label"] = lab or lab2
            else:
                group = lab or lab2
        elif hint or hint2:
            if pending:
                pending["hint"] = hint or hint2
    return out


def render(dests: list[dict]) -> str:
    lines = [START,
             "",
             "| Question | View | What it answers |",
             "|---|---|---|"]
    seen = set()
    for d in dests:
        col = d["group"] if d["group"] not in seen else ""
        seen.add(d["group"])
        lines.append(f"| {col} | [{d['label']}]({LIVE}#v={d['slug']}) | {d['hint']} |")
    lines += ["", END]
    return "\n".join(lines)


def main() -> None:
    block = render(destinations())
    if "--write" not in sys.argv:
        print(block)
        return
    text = README.read_text()
    if START not in text or END not in text:
        sys.exit(f"markers {START} / {END} not found in README.md")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    README.write_text(head + block + tail)
    print(f"wrote {len(destinations())} rows into README.md")


if __name__ == "__main__":
    main()
