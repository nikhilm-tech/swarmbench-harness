#!/usr/bin/env python3
"""
Verify that the FileSystemProvider import and reload bugs (FastMCP #3625) are fixed.
Checks import machinery (sys.path cleanup, stdlib shadowing, package root boundary)
and reload logic (race condition, deduplication, non-existent root warning).
"""
import importlib
import inspect
import os
import sys
import tempfile
import textwrap

TESTBED = "/testbed"
sys.path.insert(0, os.path.join(TESTBED, "src"))

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


# ---------------------------------------------------------------------------
# Check 1: sys.path cleaned up after non-package import
# ---------------------------------------------------------------------------
def test_sys_path_cleanup_non_package():
    from fastmcp.server.providers.filesystem_discovery import import_module_from_file
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        tool_file = Path(tmpdir) / "syspath_check_tool.py"
        tool_file.write_text("VALUE = 42\n")

        initial_len = len(sys.path)
        import_module_from_file(tool_file)

        assert len(sys.path) <= initial_len, (
            f"sys.path grew from {initial_len} to {len(sys.path)} entries "
            f"after importing a non-package file. Entries should be cleaned up."
        )


# ---------------------------------------------------------------------------
# Check 2: sys.path cleaned up after package-mode import
# ---------------------------------------------------------------------------
def test_sys_path_cleanup_package():
    from fastmcp.server.providers.filesystem_discovery import import_module_from_file
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        pkg = Path(tmpdir) / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        tool_file = pkg / "tool_in_pkg.py"
        tool_file.write_text("VALUE = 99\n")

        initial_len = len(sys.path)
        import_module_from_file(tool_file)

        assert len(sys.path) <= initial_len, (
            f"sys.path grew from {initial_len} to {len(sys.path)} entries "
            f"after importing a file inside a package. Both package-mode and "
            f"non-package-mode imports must clean up sys.path."
        )


# ---------------------------------------------------------------------------
# Check 3: sys.path cleaned up even when import raises an exception
# ---------------------------------------------------------------------------
def test_sys_path_cleanup_on_error():
    from fastmcp.server.providers.filesystem_discovery import import_module_from_file
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        bad_file = Path(tmpdir) / "bad_import.py"
        bad_file.write_text("raise RuntimeError('intentional import error')\n")

        initial_len = len(sys.path)
        try:
            import_module_from_file(bad_file)
        except Exception:
            pass

        assert len(sys.path) <= initial_len, (
            f"sys.path grew from {initial_len} to {len(sys.path)} entries "
            f"after a failed import. sys.path must be restored even when "
            f"the import raises an exception."
        )


# ---------------------------------------------------------------------------
# Check 4: stdlib module not shadowed by provider file with same name
# ---------------------------------------------------------------------------
def test_stdlib_not_shadowed():
    import json as stdlib_json

    original_dumps = stdlib_json.dumps
    assert callable(original_dumps), "stdlib json.dumps should be callable"

    from fastmcp.server.providers.filesystem_discovery import import_module_from_file
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        json_file = Path(tmpdir) / "json.py"
        json_file.write_text("PROVIDER_FILE = True\n")

        module = import_module_from_file(json_file)
        assert hasattr(module, "PROVIDER_FILE"), (
            "Provider json.py module should have PROVIDER_FILE attribute"
        )

        import json
        assert hasattr(json, "dumps"), (
            "stdlib json module no longer has 'dumps' after importing a provider "
            "file named json.py. The provider file shadowed the stdlib module."
        )
        assert json.dumps == original_dumps, (
            "json.dumps was replaced by the provider file. "
            "The sys.modules key for non-package files must not collide with stdlib."
        )


# ---------------------------------------------------------------------------
# Check 5: _find_package_root stops at provider boundary
# ---------------------------------------------------------------------------
def test_package_root_boundary():
    from fastmcp.server.providers.filesystem_discovery import _find_package_root
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        outer = Path(tmpdir) / "outer"
        inner = outer / "inner"
        inner.mkdir(parents=True)

        (outer / "__init__.py").write_text("")
        (inner / "__init__.py").write_text("")

        tool_file = inner / "my_tool.py"
        tool_file.write_text("VALUE = 1\n")

        sig = inspect.signature(_find_package_root)
        assert "stop_at" in sig.parameters or "provider_root" in sig.parameters or len(sig.parameters) >= 2, (
            "_find_package_root must accept a boundary parameter (stop_at or similar) "
            "to prevent walking above the provider root."
        )

        try:
            result = _find_package_root(tool_file, stop_at=inner)
        except TypeError:
            try:
                result = _find_package_root(tool_file, provider_root=inner)
            except TypeError:
                raise AssertionError(
                    "_find_package_root does not accept a stop_at or provider_root parameter"
                )

        assert result is not None, (
            "_find_package_root returned None but tool_file is inside a package"
        )
        assert result.resolve() == inner.resolve(), (
            f"_find_package_root returned {result} but should have stopped at {inner}. "
            f"It walked above the provider root boundary."
        )


# ---------------------------------------------------------------------------
# Check 6: import_module_from_file accepts provider_root parameter
# ---------------------------------------------------------------------------
def test_import_module_accepts_provider_root():
    from fastmcp.server.providers.filesystem_discovery import import_module_from_file
    from pathlib import Path

    sig = inspect.signature(import_module_from_file)
    assert "provider_root" in sig.parameters, (
        "import_module_from_file must accept a 'provider_root' parameter "
        "to pass as boundary to _find_package_root."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tool_file = Path(tmpdir) / "boundary_tool.py"
        tool_file.write_text("VALUE = 7\n")
        module = import_module_from_file(tool_file, provider_root=Path(tmpdir))
        assert hasattr(module, "VALUE"), (
            "import_module_from_file with provider_root failed to import the module"
        )


# ---------------------------------------------------------------------------
# Check 7: discover_and_import passes root as provider_root
# ---------------------------------------------------------------------------
def test_discover_passes_provider_root():
    from fastmcp.server.providers.filesystem_discovery import (
        discover_and_import,
        import_module_from_file,
    )
    from pathlib import Path
    from unittest.mock import patch as mock_patch

    with tempfile.TemporaryDirectory() as tmpdir:
        outer = Path(tmpdir) / "outer"
        inner = outer / "inner"
        inner.mkdir(parents=True)

        (outer / "__init__.py").write_text("")
        (inner / "__init__.py").write_text("")
        tool_file = inner / "boundary_test_tool.py"
        tool_file.write_text(textwrap.dedent("""\
            from fastmcp.tools import tool

            @tool
            def boundary_greet() -> str:
                return "hello"
        """))

        calls = []
        original_import = import_module_from_file

        def tracking_import(*args, **kwargs):
            calls.append((args, kwargs))
            return original_import(*args, **kwargs)

        with mock_patch(
            "fastmcp.server.providers.filesystem_discovery.import_module_from_file",
            tracking_import,
        ):
            discover_and_import(inner)

        assert calls, "discover_and_import did not call import_module_from_file"
        for args, kwargs in calls:
            assert "provider_root" in kwargs or len(args) >= 2, (
                "discover_and_import must pass provider_root to import_module_from_file. "
                f"Called with args={args}, kwargs={kwargs}"
            )


# ---------------------------------------------------------------------------
# Check 8: Reload lock covers both reload and read
# ---------------------------------------------------------------------------
def test_reload_race_fix():
    import asyncio
    from pathlib import Path
    from fastmcp.server.providers.filesystem import FileSystemProvider

    with tempfile.TemporaryDirectory() as tmpdir:
        tool_file = Path(tmpdir) / "race_tool.py"
        tool_file.write_text(textwrap.dedent("""\
            from fastmcp.tools import tool

            @tool
            def race_hello() -> str:
                return "hello"
        """))

        provider = FileSystemProvider(Path(tmpdir), reload=True)

        async def concurrent_reads():
            results = await asyncio.gather(
                provider._list_tools(),
                provider._list_tools(),
                provider._list_tools(),
            )
            return results

        results = asyncio.get_event_loop().run_until_complete(concurrent_reads())
        for i, r in enumerate(results):
            assert len(r) > 0, (
                f"Concurrent _list_tools() call #{i} returned empty. "
                "The reload lock must cover both the reload and the subsequent "
                "read so concurrent readers never see a cleared components dict."
            )


# ---------------------------------------------------------------------------
# Check 9: Reload lock under heavy concurrency (8 callers)
# ---------------------------------------------------------------------------
def test_reload_race_heavy():
    import asyncio
    from pathlib import Path
    from fastmcp.server.providers.filesystem import FileSystemProvider

    with tempfile.TemporaryDirectory() as tmpdir:
        tool_file = Path(tmpdir) / "heavy_tool.py"
        tool_file.write_text(textwrap.dedent("""\
            from fastmcp.tools import tool

            @tool
            def heavy_hello() -> str:
                return "hello"
        """))

        provider = FileSystemProvider(Path(tmpdir), reload=True)

        async def heavy_concurrent():
            results = await asyncio.gather(*[
                provider._list_tools() for _ in range(8)
            ])
            return results

        results = asyncio.get_event_loop().run_until_complete(heavy_concurrent())
        for i, r in enumerate(results):
            assert len(r) > 0, (
                f"Concurrent _list_tools() call #{i} of 8 returned empty. "
                "Under heavy concurrency the reload lock must still prevent "
                "any reader from observing an empty components dict."
            )


# ---------------------------------------------------------------------------
# Check 10: Concurrent reloads are deduplicated
# ---------------------------------------------------------------------------
def test_reload_deduplication():
    import asyncio
    from pathlib import Path
    from unittest.mock import patch as mock_patch
    from fastmcp.server.providers.filesystem import FileSystemProvider

    with tempfile.TemporaryDirectory() as tmpdir:
        tool_file = Path(tmpdir) / "dedup_tool.py"
        tool_file.write_text(textwrap.dedent("""\
            from fastmcp.tools import tool

            @tool
            def dedup_hello() -> str:
                return "hello"
        """))

        provider = FileSystemProvider(Path(tmpdir), reload=True)
        load_count = 0
        original_load = provider._load_components

        def counting_load():
            nonlocal load_count
            load_count += 1
            return original_load()

        with mock_patch.object(provider, "_load_components", counting_load):
            async def concurrent_reloads():
                await asyncio.gather(
                    provider._list_tools(),
                    provider._list_tools(),
                    provider._list_tools(),
                    provider._list_tools(),
                )

            asyncio.get_event_loop().run_until_complete(concurrent_reloads())

        assert load_count < 4, (
            f"_load_components was called {load_count} times for 4 concurrent "
            f"requests. Concurrent reloads must be deduplicated so that callers "
            f"waiting for the lock skip the reload if another caller already "
            f"completed one."
        )


# ---------------------------------------------------------------------------
# Check 11: Non-existent root logs a warning
# ---------------------------------------------------------------------------
def test_nonexistent_root_warning():
    import logging
    from pathlib import Path
    from fastmcp.server.providers.filesystem import FileSystemProvider

    fake_root = Path(tempfile.mkdtemp()) / "nonexistent_provider_root_42"
    assert not fake_root.exists(), "Test setup error: path must not exist"

    warning_records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.WARNING:
                warning_records.append(record)

    handler = _Capture()
    handler.setLevel(logging.WARNING)

    loggers_to_tap = [
        logging.getLogger("fastmcp.server.providers.filesystem"),
        logging.getLogger("fastmcp"),
        logging.getLogger(),
    ]
    for lg in loggers_to_tap:
        lg.addHandler(handler)
    try:
        provider = FileSystemProvider(fake_root)
        provider._load_components()
    finally:
        for lg in loggers_to_tap:
            lg.removeHandler(handler)

    assert warning_records, (
        "FileSystemProvider._load_components did not emit any logger.warning when "
        f"root path {fake_root!r} does not exist. A warning must be logged so "
        "typos in the root path are not silently ignored."
    )


# ---------------------------------------------------------------------------
# Check 12: Regression — discover_and_import still works
# ---------------------------------------------------------------------------
def test_discover_and_import_regression():
    from fastmcp.server.providers.filesystem_discovery import discover_and_import
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        tool_file = Path(tmpdir) / "regression_tool.py"
        tool_file.write_text(textwrap.dedent("""\
            from fastmcp.tools import tool

            @tool
            def regression_greet(name: str) -> str:
                return f"Hello, {name}!"
        """))

        result = discover_and_import(Path(tmpdir))
        assert len(result.components) > 0, (
            f"discover_and_import returned no components from {tmpdir}. "
            f"Failed files: {result.failed_files}. "
            f"Basic import functionality is broken."
        )
        assert len(result.failed_files) == 0, (
            f"discover_and_import had import failures: {result.failed_files}"
        )


check("sys.path cleanup after non-package import", test_sys_path_cleanup_non_package)
check("sys.path cleanup after package-mode import", test_sys_path_cleanup_package)
check("sys.path cleanup when import raises exception", test_sys_path_cleanup_on_error)
check("stdlib json not shadowed by provider file", test_stdlib_not_shadowed)
check("_find_package_root stops at provider boundary", test_package_root_boundary)
check("import_module_from_file accepts provider_root", test_import_module_accepts_provider_root)
check("discover_and_import passes provider_root", test_discover_passes_provider_root)
check("Reload lock covers both reload and read", test_reload_race_fix)
check("Reload lock under heavy concurrency", test_reload_race_heavy)
check("Concurrent reloads are deduplicated", test_reload_deduplication)
check("Non-existent root logs a warning", test_nonexistent_root_warning)
check("Regression: discover_and_import still works", test_discover_and_import_regression)

reward = passed / total
print(f"\nResult: {passed}/{total} checks passed")
print(f"Reward: {reward:.4f}")

os.makedirs("/logs/verifier", exist_ok=True)
with open("/logs/verifier/reward.txt", "w") as f:
    f.write(str(reward))

sys.exit(0)
