"""
check_routes.py -- Generic route smoke test.

Uses Flask's built-in test client (no running server needed). Discovers
every GET-capable route from the app's own url_map (no per-project route
list to maintain) and checks that none of them raise an unhandled server
error. A redirect (e.g. a session-gated route bouncing to a start page
with no session set) is expected and not a failure -- only a 5xx response
counts as broken.

This generic version deliberately does NOT assert project-specific page
content (exact headings, form field names, calculation results) -- that
requires knowing the project's actual pages and session model, which this
starter can't know in advance. Two extension points below let a project
layer that on once it exists, without losing the generic baseline check:

  CONTENT_ASSERTIONS -- map a route to substrings its rendered body must
    contain (checked with an empty/fresh session).
  SEEDED_SESSION / SEEDED_ASSERTIONS -- a session dict to seed before
    testing SEEDED_ASSERTIONS' routes, for pages that only render with
    session state already present (e.g. a Results page).

Both are empty by default -- fill them in once your project's session
model and page content are settled (WBS.md Phase 3/4) for stronger
coverage than the generic 5xx-only check.

Exit 0 = all checks pass; 1 = any failure.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from app import create_app
except Exception as e:
    print(f'FAIL  Could not import app: {e}')
    sys.exit(1)

# ---------------------------------------------------------------------------
# Optional per-project extension points -- see module docstring. Empty by
# default; the generic discovery-based check below works with no changes.
# ---------------------------------------------------------------------------
CONTENT_ASSERTIONS = {
    # '/profile': ['company', 'industry'],
}
SEEDED_SESSION = {
    # 'profile': {...}, 'results': {...},
}
SEEDED_ASSERTIONS = {
    # '/results': ['your score'],
}


def discover_get_routes(app):
    routes = []
    for rule in app.url_map.iter_rules():
        if 'GET' not in rule.methods:
            continue
        if rule.rule.startswith('/static'):
            continue
        if '<' in rule.rule:
            continue  # skip routes needing a URL parameter -- can't smoke-test generically
        routes.append(rule.rule)
    return sorted(set(routes))


def check_route(client, route, expected, fail_list, allow_redirect=True):
    try:
        resp = client.get(route)
        if resp.status_code >= 500:
            print(f'  FAIL  GET {route} -- server error {resp.status_code}')
            fail_list.append(route)
            return
        if resp.status_code not in (200, 301, 302) or (resp.status_code != 200 and not allow_redirect):
            print(f'  FAIL  GET {route} -- unexpected status {resp.status_code}')
            fail_list.append(route)
            return
        if resp.status_code == 200 and expected:
            body = resp.data.decode('utf-8', errors='replace').lower()
            missing = [s for s in expected if s.lower() not in body]
            if missing:
                print(f'  FAIL  GET {route} -- expected strings missing: {missing}')
                fail_list.append(route)
                return
        loc = f' -> {resp.headers.get("Location", "")}' if resp.status_code in (301, 302) else ''
        print(f'  OK    GET {route}  ({resp.status_code}){loc}')
    except Exception as e:
        print(f'  FAIL  GET {route} -- exception: {e}')
        fail_list.append(route)


def main():
    app = create_app()
    app.config['TESTING'] = True

    print('Route smoke test')
    failures = []

    routes = discover_get_routes(app)
    if not routes:
        print('  WARN  No GET routes discovered (no blueprint registered yet?)')

    # -- Generic pass: every discovered route, fresh session, 5xx = fail,
    #    plus any CONTENT_ASSERTIONS the project has filled in.
    with app.test_client() as client:
        for route in routes:
            if route in SEEDED_ASSERTIONS:
                continue  # handled in the seeded pass below
            check_route(client, route, CONTENT_ASSERTIONS.get(route), failures)

    # -- Seeded pass: only runs if the project has filled in SEEDED_SESSION
    #    and SEEDED_ASSERTIONS.
    if SEEDED_ASSERTIONS:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.update(SEEDED_SESSION)
            for route, expected in SEEDED_ASSERTIONS.items():
                check_route(client, route, expected, failures, allow_redirect=False)

    print()
    if failures:
        print(f'RESULT: FAIL -- {len(failures)} check(s) did not pass')
        sys.exit(1)
    else:
        print(f'RESULT: PASS -- {len(routes)} route(s) smoke-tested clean')
        sys.exit(0)


if __name__ == '__main__':
    main()
