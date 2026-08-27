"""
check_css.py -- Verify every CSS class used in a template is defined
somewhere it can actually reach: that template's own <style> block, or an
ancestor template it {% extends %}.

Templates are auto-discovered under app/templates/<blueprint>/ for every
blueprint under app/blueprints/ -- no per-project file list to maintain.

Two architectures are both supported automatically:
  - Self-contained pages (each template has its own <style>, no
    {% extends %}): coverage is checked per-file.
  - Shared base.html (child templates use {% extends "base.html" %} and
    rely on the parent's CSS): a child's used classes are checked against
    the UNION of its own <style> block and every ancestor's, walking the
    extends chain.
Which one a given project uses is discovered per-file from the templates
themselves -- nothing to configure.

Exit code 0 = all classes covered; 1 = gaps found.
"""

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Classes toggled purely via JS (classList.add/remove, never present in a
# template's own class="..." attributes at rest) go here if a real FAIL
# below turns out to be a false positive for this project. Left empty by
# default -- fill in only after seeing an actual FAIL, not preemptively.
IGNORE = set()

class_attr_re = re.compile(r'class="([^"]*)"')
jinja_expr_re = re.compile(r'\{[{%]')
script_re     = re.compile(r'<script\b[^>]*>.*?</script>', re.DOTALL)
extends_re    = re.compile(r'\{%-?\s*extends\s+["\']([^"\']+)["\']\s*-?%\}')
style_re      = re.compile(r'<style\b[^>]*>(.*?)</style>', re.DOTALL)


def discover_templates():
    templates = {}
    templates_dir = BASE_DIR / 'app' / 'templates'
    if templates_dir.is_dir():
        for html_file in sorted(templates_dir.glob('**/*.html')):
            templates[html_file.name] = html_file
    return templates


def extract_used_classes(text):
    # Strip <script> blocks first -- pages that build HTML via JS string
    # concatenation or template literals (e.g. '<div class="' + x + '">')
    # would otherwise get misparsed as real class="..." markup by the
    # naive regex below. Only literal HTML markup should count.
    html_only = script_re.sub('', text)
    used = set()
    for m in class_attr_re.finditer(html_only):
        val = m.group(1)
        jm = jinja_expr_re.search(val)
        static_part = val[:jm.start()] if jm else val
        for cls in static_part.split():
            used.add(cls)
    return used


def extract_defined_classes(text):
    defined = set()
    for style_block in style_re.findall(text):
        defined |= {m.group(1) for m in re.finditer(r'\.([\w-]+)', style_block)}
    return defined


def resolve_ancestor_chain(name, templates, seen=None):
    """Follow {% extends "X" %} from `name` up through its ancestors.
    Returns the list of template names in the chain, [name, parent, ...],
    stopping at a name not found on disk or a cycle."""
    seen = seen or []
    if name in seen or name not in templates:
        return seen
    seen = seen + [name]
    text = templates[name].read_text(encoding='utf-8', errors='replace')
    m = extends_re.search(text)
    if not m:
        return seen
    parent_ref = m.group(1)
    parent_name = Path(parent_ref).name  # extends refs may include a path prefix
    if parent_name not in templates or parent_name in seen:
        return seen
    return resolve_ancestor_chain(parent_name, templates, seen)


def main():
    templates = discover_templates()
    if not templates:
        print('No templates found under app/templates/<blueprint>/')
        sys.exit(0)

    print('CSS coverage check')
    fail = False
    for name, path in sorted(templates.items()):
        text = path.read_text(encoding='utf-8', errors='replace')
        chain = resolve_ancestor_chain(name, templates)

        used = extract_used_classes(text) - IGNORE
        defined = set()
        for chain_name in chain:
            defined |= extract_defined_classes(
                templates[chain_name].read_text(encoding='utf-8', errors='replace')
            )

        if not defined:
            print(f'  FAIL  {name}  -- no <style> block found in {name} or its extends chain {chain}')
            fail = True
            continue

        missing = sorted(used - defined)
        chain_note = f'  (extends chain: {" -> ".join(chain)})' if len(chain) > 1 else ''
        if missing:
            print(f'  FAIL  {name}  ({len(missing)} missing of {len(used)} used, {len(defined)} defined){chain_note}')
            for cls in missing:
                print(f'    .{cls}')
            fail = True
        else:
            print(f'  OK    {name}  ({len(used)} used, {len(defined)} defined){chain_note}')

    print()
    if fail:
        print('RESULT: FAIL -- add missing rules, or extend IGNORE if truly JS-only, before deploying')
        sys.exit(1)
    else:
        print('RESULT: PASS -- all template classes are defined in their own style or an ancestor template')
        sys.exit(0)


if __name__ == '__main__':
    main()
