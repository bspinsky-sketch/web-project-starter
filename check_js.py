"""
check_js.py -- Verify every JS function referenced from an inline event
attribute (onclick=, onsubmit=, etc.) in a template is defined somewhere it
can actually reach: that template's own <script> block(s), or an ancestor
template it {% extends %}.

Templates are auto-discovered under app/templates/<blueprint>/ for every
blueprint under app/blueprints/ -- no per-project file list to maintain.
Same extends-chain resolution as check_css.py, so this works whether the
project uses a shared base.html or fully self-contained pages.

Exit 0 = all calls covered; 1 = gaps found.
"""

import re, sys
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Browser/runtime builtins that can legitimately appear in an inline handler.
GLOBAL_FUNS = {
    'alert', 'confirm', 'console', 'setTimeout', 'setInterval', 'clearTimeout',
    'parseInt', 'parseFloat', 'Math', 'JSON', 'Object', 'Array', 'String',
    'Number', 'document', 'window', 'fetch', 'Promise', 'encodeURIComponent',
}

extends_re = re.compile(r'\{%-?\s*extends\s+["\']([^"\']+)["\']\s*-?%\}')


def discover_templates():
    templates = {}
    templates_dir = BASE_DIR / 'app' / 'templates'
    if templates_dir.is_dir():
        for html_file in sorted(templates_dir.glob('**/*.html')):
            templates[html_file.name] = html_file
    return templates


def resolve_ancestor_chain(name, templates, seen=None):
    seen = seen or []
    if name in seen or name not in templates:
        return seen
    seen = seen + [name]
    text = templates[name].read_text(encoding='utf-8', errors='replace')
    m = extends_re.search(text)
    if not m:
        return seen
    parent_name = Path(m.group(1)).name
    if parent_name not in templates or parent_name in seen:
        return seen
    return resolve_ancestor_chain(parent_name, templates, seen)


def extract_calls(text):
    calls = set()
    for attr in re.findall(r'on\w+="([^"]*)"', text):
        for name in re.findall(r'\b([a-zA-Z_]\w*)\s*\(', attr):
            calls.add(name)
    return calls


def extract_definitions(text):
    defs = set()
    for script in re.findall(r'<script[^>]*>(.*?)</script>', text, re.DOTALL):
        for name in re.findall(r'function\s+([a-zA-Z_]\w*)\s*\(', script):
            defs.add(name)
    return defs


def main():
    templates = discover_templates()
    if not templates:
        print('No templates found under app/templates/<blueprint>/')
        sys.exit(0)

    print('JS function check (inline event handlers only)')
    fail = False
    total_calls = 0
    for name, path in sorted(templates.items()):
        text = path.read_text(encoding='utf-8', errors='replace')
        chain = resolve_ancestor_chain(name, templates)

        calls = extract_calls(text)
        defs = set(GLOBAL_FUNS)
        for chain_name in chain:
            defs |= extract_definitions(
                templates[chain_name].read_text(encoding='utf-8', errors='replace')
            )

        missing = sorted(c for c in calls if c not in defs)
        total_calls += len(calls)
        chain_note = f'  (extends chain: {" -> ".join(chain)})' if len(chain) > 1 else ''
        if missing:
            print(f'  FAIL  {name}{chain_note}')
            for m in missing:
                print(f'    {m}() called but not defined in {name} or its extends chain')
            fail = True
        elif calls:
            print(f'  OK    {name}  ({len(calls)} call(s) verified){chain_note}')
        else:
            print(f'  OK    {name}  (no inline event handlers)')

    print()
    if fail:
        print('RESULT: FAIL -- undefined JS functions found')
        sys.exit(1)
    else:
        print(f'RESULT: PASS -- all {total_calls} inline JS function call(s) are defined')
        sys.exit(0)


if __name__ == '__main__':
    main()
