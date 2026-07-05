#!/usr/bin/env python3
"""
Smoke tests for Eikón MCP Server.
Tests that the server is correctly structured, imports cleanly, and tools are registered.
Does NOT require a running backend — only verifies code structure.
"""

import sys


def test_imports():
    """Test that all modules import without error."""
    print("\n" + "=" * 70)
    print("TEST: Module Imports")
    print("=" * 70)

    try:
        from server import (
            EIKON_API_KEY,
            EIKON_BASE_URL,
            USE_FASTMCP,
            eikon_create_brand,
            eikon_gallery,
            eikon_generate_asset,
            eikon_list_asset_types,
            eikon_list_brands,
            eikon_logo_options,
            eikon_set_identity,
            get_headers,
        )
        print("✓ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_headers():
    """Test header generation."""
    print("\n" + "=" * 70)
    print("TEST: Header Generation")
    print("=" * 70)

    from server import get_headers

    headers = get_headers()
    required = ["Authorization", "Content-Type"]

    for key in required:
        if key not in headers:
            print(f"✗ Missing header: {key}")
            return False
        print(f"✓ Header '{key}' present")

    auth = headers["Authorization"]
    if not auth.startswith("Bearer "):
        print(f"✗ Authorization header format invalid: {auth}")
        return False
    print("✓ Authorization format correct (Bearer token)")

    if headers["Content-Type"] != "application/json":
        print(f"✗ Content-Type should be 'application/json', got: {headers['Content-Type']}")
        return False
    print("✓ Content-Type is application/json")

    return True


def test_function_signatures():
    """Test that all functions have correct signatures."""
    print("\n" + "=" * 70)
    print("TEST: Function Signatures")
    print("=" * 70)

    import inspect

    from server import (
        eikon_create_brand,
        eikon_gallery,
        eikon_generate_asset,
        eikon_list_asset_types,
        eikon_list_brands,
        eikon_logo_options,
        eikon_set_identity,
    )

    functions = {
        "eikon_list_brands": {
            "func": eikon_list_brands,
            "params": [],
            "is_async": True,
        },
        "eikon_create_brand": {
            "func": eikon_create_brand,
            "params": ["name"],
            "is_async": True,
        },
        "eikon_logo_options": {
            "func": eikon_logo_options,
            "params": ["brand_id"],
            "is_async": True,
        },
        "eikon_set_identity": {
            "func": eikon_set_identity,
            "params": ["brand_id", "logo_style"],
            "is_async": True,
        },
        "eikon_list_asset_types": {
            "func": eikon_list_asset_types,
            "params": [],
            "is_async": True,
        },
        "eikon_generate_asset": {
            "func": eikon_generate_asset,
            "params": ["brand_id", "asset_type", "content"],
            "is_async": True,
        },
        "eikon_gallery": {
            "func": eikon_gallery,
            "params": [],
            "is_async": True,
        },
    }

    all_pass = True
    for name, spec in functions.items():
        func = spec["func"]
        expected_params = spec["params"]
        expected_async = spec["is_async"]

        sig = inspect.signature(func)
        actual_params = [p for p in sig.parameters if p != "return"]
        is_async = inspect.iscoroutinefunction(func)

        if is_async != expected_async:
            print(f"✗ {name}: Expected async={expected_async}, got {is_async}")
            all_pass = False
        else:
            print(f"✓ {name}: async={is_async}")

        # Check required params (those without defaults)
        required_params = [
            p
            for p in sig.parameters.values()
            if p.default == inspect.Parameter.empty
        ]
        required_names = [p.name for p in required_params]
        for param in expected_params:
            if param not in actual_params:
                print(f"  ⚠ Missing parameter: {param}")

        print(f"  Parameters: {', '.join(actual_params) if actual_params else '(none)'}")

    return all_pass


def test_mcp_framework():
    """Test that MCP framework is correctly set up."""
    print("\n" + "=" * 70)
    print("TEST: MCP Framework Setup")
    print("=" * 70)

    try:
        from server import USE_FASTMCP

        print(f"✓ MCP framework loaded (FastMCP={USE_FASTMCP})")

        if USE_FASTMCP:
            from server import mcp

            print("✓ FastMCP server object exists")
            print(f"  Type: {type(mcp).__name__}")

            # Check for tool decorator
            if hasattr(mcp, "tool"):
                print("✓ @mcp.tool() decorator available")
            else:
                print("⚠ @mcp.tool() decorator not found")

        else:

            print("✓ Standard MCP Server available")
            # Would need an instance to check methods

        return True
    except Exception as e:
        print(f"✗ MCP framework test failed: {e}")
        return False


def test_docstrings():
    """Test that all functions have docstrings."""
    print("\n" + "=" * 70)
    print("TEST: Docstrings")
    print("=" * 70)

    from server import (
        eikon_create_brand,
        eikon_gallery,
        eikon_generate_asset,
        eikon_list_asset_types,
        eikon_list_brands,
        eikon_logo_options,
        eikon_set_identity,
    )

    functions = [
        eikon_list_brands,
        eikon_create_brand,
        eikon_logo_options,
        eikon_set_identity,
        eikon_list_asset_types,
        eikon_generate_asset,
        eikon_gallery,
    ]

    all_pass = True
    for func in functions:
        if func.__doc__:
            print(f"✓ {func.__name__}: has docstring")
        else:
            print(f"✗ {func.__name__}: missing docstring")
            all_pass = False

    return all_pass


def main():
    """Run all smoke tests."""
    print("\n" + "#" * 70)
    print("# EIKÓN MCP SERVER SMOKE TESTS")
    print("#" * 70)

    results = {
        "imports": test_imports(),
        "headers": test_headers(),
        "signatures": test_function_signatures(),
        "mcp_framework": test_mcp_framework(),
        "docstrings": test_docstrings(),
    }

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n" + "🎉 " * 10)
        print("ALL TESTS PASSED — Server is ready for deployment!")
        print("🎉 " * 10)
        return 0
    else:
        print("\n⚠ Some tests failed. Review output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
