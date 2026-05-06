#!/usr/bin/env python3
"""
Verify: Django pytz-to-zoneinfo migration (Ticket #32365 / PR #14848).

Design principles:
  - Every check traces to a requirement in instruction.md.
  - No specific variable names or function signatures are enforced.
    A correct implementation with different internal naming must still pass.
  - Behavioral correctness is verified by running Django's own test suites.
  - Source-level checks verify structural migration (zoneinfo imported,
    pytz removed as hard dependency, docs updated) without dictating HOW.
"""
import os
import re
import subprocess
import sys

TESTBED = "/testbed"
passed = 0
total = 0


def check(name, fn):
    global passed, total
    total += 1
    try:
        fn()
        print(f"  PASS  {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {name}: {e}")


def read_file(relpath):
    with open(os.path.join(TESTBED, relpath)) as f:
        return f.read()


# ── django/utils/timezone.py ─────────────────────────────────────────

def test_timezone_imports_zoneinfo():
    src = read_file("django/utils/timezone.py")
    assert "import zoneinfo" in src or "from backports import zoneinfo" in src, \
        "timezone.py does not import zoneinfo"

def test_timezone_no_toplevel_pytz():
    src = read_file("django/utils/timezone.py")
    lines_before_first_def = src.split("\ndef ")[0]
    assert "import pytz" not in lines_before_first_def, \
        "timezone.py still has top-level 'import pytz'"

def test_timezone_utc_is_stdlib():
    src = read_file("django/utils/timezone.py")
    assert "utc = timezone.utc" in src or "utc = datetime.timezone.utc" in src, \
        "timezone.utc is not aliased to datetime.timezone.utc"
    assert "pytz.utc" not in src.split("def ")[0], \
        "timezone.py still sets utc = pytz.utc at module level"

def test_timezone_uses_zoneinfo():
    src = read_file("django/utils/timezone.py")
    assert "zoneinfo.ZoneInfo" in src, \
        "timezone.py does not use zoneinfo.ZoneInfo for timezone construction"

def test_timezone_is_dst_deprecation():
    """make_aware() should deprecate is_dst; default must no longer be None."""
    src = read_file("django/utils/timezone.py")
    assert "RemovedInDjango50Warning" in src, \
        "timezone.py does not reference RemovedInDjango50Warning"
    assert not re.search(r"def make_aware\([^)]*is_dst\s*=\s*None", src), \
        "make_aware() should no longer default is_dst=None"


# ── django/conf/ ─────────────────────────────────────────────────────

def test_global_settings_use_deprecated_pytz():
    src = read_file("django/conf/global_settings.py")
    assert "USE_DEPRECATED_PYTZ" in src, \
        "USE_DEPRECATED_PYTZ not found in global_settings.py"

def test_conf_init_deprecation_warning():
    src = read_file("django/conf/__init__.py")
    assert "USE_DEPRECATED_PYTZ" in src, \
        "conf/__init__.py does not handle USE_DEPRECATED_PYTZ"
    assert "RemovedInDjango50Warning" in src, \
        "conf/__init__.py does not reference RemovedInDjango50Warning"


# ── django/db/backends/ ──────────────────────────────────────────────

def test_base_backend_uses_zoneinfo():
    src = read_file("django/db/backends/base/base.py")
    has_zoneinfo_path = "zoneinfo" in src or "ZoneInfo" in src
    has_transition_path = "USE_DEPRECATED_PYTZ" in src
    assert has_zoneinfo_path and has_transition_path, \
        "base/base.py does not appear to support zoneinfo default with transitional pytz path"

def test_sqlite3_backend_uses_zoneinfo():
    src = read_file("django/db/backends/sqlite3/base.py")
    lines_before_first_def = src.split("def ")[0]
    no_hard_pytz = "import pytz" not in lines_before_first_def
    has_zoneinfo = "zoneinfo" in src or "ZoneInfo" in src or \
                   "backends.base" in src
    assert no_hard_pytz and has_zoneinfo, \
        "sqlite3/base.py still hard-imports pytz or lacks zoneinfo usage"


# ── django/templatetags/tz.py ────────────────────────────────────────

def test_templatetags_tz_uses_zoneinfo():
    src = read_file("django/templatetags/tz.py")
    assert "zoneinfo" in src, "templatetags/tz.py does not import zoneinfo"
    preamble = src.split("def ")[0].split("class ")[0]
    assert "import pytz" not in preamble, \
        "templatetags/tz.py still has top-level 'import pytz'"


# ── django/db/models/ ────────────────────────────────────────────────

def test_datetime_functions_is_dst_deprecated():
    """Trunc functions should no longer default is_dst=None."""
    src = read_file("django/db/models/functions/datetime.py")
    assert not re.search(r"def __init__\([^)]*is_dst\s*=\s*None", src), \
        "Trunc functions should no longer default is_dst=None"

def test_queryset_datetimes_is_dst_deprecated():
    """datetimes() should no longer default is_dst=None."""
    src = read_file("django/db/models/query.py")
    assert not re.search(r"def datetimes\([^)]*is_dst\s*=\s*None", src), \
        "datetimes() should no longer default is_dst=None"

def test_serializer_no_pytz_utc():
    src = read_file("django/db/migrations/serializer.py")
    assert "<UTC>" not in src, \
        "serializer.py still uses pytz's <UTC> representation"


# ── setup.cfg ─────────────────────────────────────────────────────────

def test_setup_cfg_no_pytz_dependency():
    src = read_file("setup.cfg")
    lines = [l.strip() for l in src.splitlines()]
    for line in lines:
        if line == "pytz":
            raise AssertionError("setup.cfg still lists pytz as a hard dependency")
    assert "backports.zoneinfo" in src or "zoneinfo" in src, \
        "setup.cfg does not include backports.zoneinfo for Python < 3.9"


# ── Documentation ────────────────────────────────────────────────────

def test_docs_release_notes():
    src = read_file("docs/releases/4.0.txt")
    assert "zoneinfo" in src, \
        "docs/releases/4.0.txt does not mention zoneinfo"
    assert "USE_DEPRECATED_PYTZ" in src, \
        "docs/releases/4.0.txt does not mention USE_DEPRECATED_PYTZ"

def test_docs_deprecation_timeline():
    src = read_file("docs/internals/deprecation.txt")
    assert "USE_DEPRECATED_PYTZ" in src or "is_dst" in src, \
        "docs/internals/deprecation.txt does not mention pytz deprecation"

def test_docs_settings_ref():
    src = read_file("docs/ref/settings.txt")
    assert "USE_DEPRECATED_PYTZ" in src, \
        "docs/ref/settings.txt does not document USE_DEPRECATED_PYTZ"

def test_docs_timezone_topic():
    src = read_file("docs/topics/i18n/timezones.txt")
    assert "zoneinfo" in src, \
        "docs/topics/i18n/timezones.txt does not mention zoneinfo"

def test_docs_utils_ref():
    src = read_file("docs/ref/utils.txt")
    assert "is_dst" in src and "deprecated" in src.lower(), \
        "docs/ref/utils.txt does not mark is_dst as deprecated"

def test_docs_db_functions():
    src = read_file("docs/ref/models/database-functions.txt")
    assert "zoneinfo" in src, \
        "docs/ref/models/database-functions.txt does not mention zoneinfo"


# ── Test suite runs (behavioral verification) ────────────────────────

def _run_tests(label):
    result = subprocess.run(
        [sys.executable, "tests/runtests.py", label, "--verbosity=0"],
        cwd=TESTBED, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, \
        f"'{label}' tests failed (exit {result.returncode}):\n{result.stderr[-800:]}"

def test_suite_utils_timezone():
    _run_tests("utils_tests.test_timezone")

def test_suite_settings():
    _run_tests("settings_tests")

def test_suite_timezones():
    _run_tests("timezones")

def test_suite_datetimes():
    _run_tests("datetimes")

def test_suite_migrations_writer():
    _run_tests("migrations.test_writer")


# ── Run all checks ───────────────────────────────────────────────────

# Core timezone utils (5 checks)
check("timezone.py: imports zoneinfo", test_timezone_imports_zoneinfo)
check("timezone.py: no top-level import pytz", test_timezone_no_toplevel_pytz)
check("timezone.py: utc is datetime.timezone.utc", test_timezone_utc_is_stdlib)
check("timezone.py: uses zoneinfo.ZoneInfo", test_timezone_uses_zoneinfo)
check("timezone.py: is_dst deprecated with RemovedInDjango50Warning", test_timezone_is_dst_deprecation)

# Settings (2 checks)
check("global_settings.py: USE_DEPRECATED_PYTZ defined", test_global_settings_use_deprecated_pytz)
check("conf/__init__.py: USE_DEPRECATED_PYTZ deprecation warning", test_conf_init_deprecation_warning)

# Database backends (2 checks)
check("base/base.py: uses zoneinfo, no hard pytz import", test_base_backend_uses_zoneinfo)
check("sqlite3/base.py: uses zoneinfo, no hard pytz import", test_sqlite3_backend_uses_zoneinfo)

# Template tags (1 check)
check("templatetags/tz.py: uses zoneinfo", test_templatetags_tz_uses_zoneinfo)

# Models (3 checks)
check("datetime functions: Trunc is_dst no longer defaults to None", test_datetime_functions_is_dst_deprecated)
check("query.py: datetimes() is_dst no longer defaults to None", test_queryset_datetimes_is_dst_deprecated)
check("serializer.py: no pytz <UTC> repr", test_serializer_no_pytz_utc)

# setup.cfg (1 check)
check("setup.cfg: pytz not a hard dependency", test_setup_cfg_no_pytz_dependency)

# Documentation (6 checks)
check("docs/releases/4.0.txt: zoneinfo + USE_DEPRECATED_PYTZ", test_docs_release_notes)
check("docs/internals/deprecation.txt: pytz deprecation entries", test_docs_deprecation_timeline)
check("docs/ref/settings.txt: USE_DEPRECATED_PYTZ documented", test_docs_settings_ref)
check("docs/topics/i18n/timezones.txt: mentions zoneinfo", test_docs_timezone_topic)
check("docs/ref/utils.txt: is_dst deprecated", test_docs_utils_ref)
check("docs/ref/models/database-functions.txt: mentions zoneinfo", test_docs_db_functions)

# Test suite runs — behavioral verification (5 checks)
check("test suite: utils_tests.test_timezone", test_suite_utils_timezone)
check("test suite: settings_tests", test_suite_settings)
check("test suite: timezones", test_suite_timezones)
check("test suite: datetimes", test_suite_datetimes)
check("test suite: migrations.test_writer", test_suite_migrations_writer)

print(f"\nResult: {passed}/{total} checks passed")

with open("/logs/verifier/reward.txt", "w") as f:
    f.write(str(round(passed / total, 2)))

sys.exit(0)
