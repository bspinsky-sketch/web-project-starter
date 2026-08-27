"""
check_structure.py -- Detect middle-truncation by comparing structural fingerprints.

After every verified write, run with --update to store a new baseline.
On every check run, compares current counts against baseline and flags drops.

This project's blueprint is auto-discovered -- no per-project file list to
maintain. Discovery assumes the standard layout this starter produces:
  app/blueprints/<blueprint>/*.py        (blueprint modules)
  app/templates/<blueprint>/**/*.html    (that blueprint's templates)
where <blueprint> is whatever the single subfolder under app/blueprints/
was renamed to during project setup (README_first.md step 2). If more than
one blueprint folder exists, all of them are included.

Structural markers counted per file:
  .html templates : CSS class definitions (that file's own <style> block),
                     CSS rule count, JS function definitions, Jinja2
                     block/for/if tags
  .py modules     : function definitions (def ), class definitions
                     (class ), @bp.route(...) decorator count

Usage:
  python3 check_structure.py          # compare against baseline
  python3 check_structure.py --update # rewrite baseline from current files
"""

import re, sys, json
from pathlib import Path

BASE_DIR  = Path(__file__).parent
BASELINE  = BASE_DIR / '.check_baseline.json'


def discover_files():
    """Find every blueprint's .py modules and .html templates. Paths are
    returned relative to BASE_DIR, sorted for stable ordering."""
    files = {}

    blueprints_dir = BASE_DIR / 'app' / 'blueprints'
    if blueprints_dir.is_dir():
        for bp_dir in sorted(blueprints_dir.iterdir()):
            if not bp_dir.is_dir() or bp_dir.name == '__pycache__':
                continue
            for py_file in sorted(bp_dir.glob('*.py')):
                rel = py_file.relative_to(BASE_DIR).as_posix()
                files[rel] = 'py'

    templates_dir = BASE_DIR / 'app' / 'templates'
    if templates_dir.is_dir():
        for html_file in sorted(templates_dir.glob('**/*.html')):
            rel = html_file.relative_to(BASE_DIR).as_posix()
            files[rel] = 'html'

    return files


def fingerprint(path_str, kind):
    path = BASE_DIR / path_str
    text = path.read_text(encoding='utf-8', errors='replace')
    fp = {'lines': text.count('\n')}

    if kind == 'html':
        fp['jinja_for']       = len(re.findall(r'\{%-?\s*for\b',     text))
        fp['jinja_endfor']    = len(re.findall(r'\{%-?\s*endfor\b',  text))
        fp['jinja_if']        = len(re.findall(r'\{%-?\s*if\b',      text))
        fp['jinja_endif']     = len(re.findall(r'\{%-?\s*endif\b',   text))
        fp['jinja_block']     = len(re.findall(r'\{%-?\s*block\b',   text))
        fp['jinja_endblock']  = len(re.findall(r'\{%-?\s*endblock\b',text))
        fp['css_classes']     = len(re.findall(r'\.([\w-]+)\s*\{',   text))
        style = re.search(r'<style>(.*?)</style>', text, re.DOTALL)
        fp['css_rules']       = text.count('{') - text.count('{{')
        fp['css_class_count'] = len(re.findall(r'\.([\w-]+)', style.group(1))) if style else 0
        fp['js_functions']    = len(re.findall(r'function\s+\w+\s*\(', text))

    elif kind == 'py':
        fp['functions'] = len(re.findall(r'^\s*def \w+', text, re.MULTILINE))
        fp['classes']   = len(re.findall(r'^\s*class \w+', text, re.MULTILINE))
        fp['routes']    = len(re.findall(r'@\w+\.route\(', text))

    return fp


def load_baseline():
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text())


def save_baseline(data):
    BASELINE.write_text(json.dumps(data, indent=2))


def compare(current, stored):
    issues = []
    for metric, cur_val in current.items():
        if metric not in stored:
            continue
        stored_val = stored[metric]
        if cur_val < stored_val:
            issues.append(f'  {metric}: was {stored_val}, now {cur_val} (DROP OF {stored_val - cur_val})')
    return issues


def main():
    update_mode = '--update' in sys.argv

    files = discover_files()
    if not files:
        print('No blueprint templates or modules found under app/blueprints/ or app/templates/')
        print('Skipping structural check')
        sys.exit(0)

    if update_mode:
        baseline = {}
        for path_str, kind in files.items():
            baseline[path_str] = fingerprint(path_str, kind)
        save_baseline(baseline)
        print(f'Baseline updated -- {len(files)} files fingerprinted')
        for f, fp in baseline.items():
            print(f'  {f}: {fp}')
        sys.exit(0)

    baseline = load_baseline()
    if not baseline:
        print('No baseline found -- run with --update after a verified-good state')
        print('Skipping structural check')
        sys.exit(0)

    print('Structural integrity check')
    fail = False
    for path_str, kind in files.items():
        current = fingerprint(path_str, kind)
        stored  = baseline.get(path_str, {})
        if not stored:
            print(f'  NO BASELINE  {path_str}  (new file since last --update)')
            continue
        issues = compare(current, stored)
        if issues:
            print(f'  FAIL  {path_str}')
            for issue in issues:
                print(issue)
            fail = True
        else:
            print(f'  OK    {path_str}')

    for path_str in baseline:
        if path_str not in files:
            print(f'  MISSING  {path_str}  (in baseline but no longer found on disk)')
            fail = True

    print()
    if fail:
        print('RESULT: FAIL -- structural drop detected; possible middle truncation')
        sys.exit(1)
    else:
        print('RESULT: PASS -- all structural counts at or above baseline')
        sys.exit(0)


if __name__ == '__main__':
    main()
