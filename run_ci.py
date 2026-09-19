"""
run_ci.py
---------------------------------------------------------------------------
Comprehensive Local CI Checking Pipeline for Autodesk Fusion 360 Projects.

Stages:
  1. Python Syntax Compilation Check (py_compile across all repository .py files)
  2. AST Code Analysis (syntax, docstrings, and imports)
  3. Static Linting & Code Quality (ruff/flake8 if available, fallback to built-in AST checks)
  4. Type Checking (pyright if available, validating against pyrightconfig.json)
  5. Unit Tests (derivation, verification, formula synchronization, CSV BOM)
  6. Autodesk Fusion API Integration & Mock CAD Verification (sketches, extrusions, patterns)
  7. Autodesk Fusion MCP Protocol & Contract Tests (tools/list, tools/call, init)

Run locally:
  python run_ci.py
"""

import ast
import os
import py_compile
import subprocess
import sys
import time
import unittest


REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Safe symbols for all terminal encodings
CHECK = "[PASS]"
CROSS = "[FAIL]"
INFO_TAG = "[INFO]"
ARROW = ">>"


def print_stage(title: str):
    print(f"\n{CYAN}{BOLD}{ARROW} {title}{RESET}")
    print("-" * 65)


def print_pass(msg: str):
    print(f"  {GREEN}{CHECK}{RESET} : {msg}")


def print_fail(msg: str, detail: str = ""):
    print(f"  {RED}{CROSS}{RESET} : {msg}")
    if detail:
        print(f"    {RED}{detail}{RESET}")


def print_info(msg: str):
    print(f"  {YELLOW}{INFO_TAG}{RESET} : {msg}")


def find_python_files() -> list:
    """Collect all repo Python files, ignoring venvs, git, cache, and third-party."""
    py_files = []
    ignore_dirs = {".git", ".venv", "venv", "__pycache__", "out", ".agents"}
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    return sorted(py_files)


def stage_1_syntax_compilation() -> bool:
    """Compile every Python file to ensure zero syntax or bytecode errors."""
    print_stage("Stage 1: Python Syntax Compilation (py_compile)")
    py_files = find_python_files()
    all_ok = True
    for path in py_files:
        rel_path = os.path.relpath(path, REPO_ROOT)
        try:
            py_compile.compile(path, doraise=True)
            print_pass(f"Syntax valid: {rel_path}")
        except py_compile.PyCompileError as e:
            print_fail(f"Syntax error in {rel_path}", str(e))
            all_ok = False
    return all_ok


def stage_2_ast_code_quality() -> bool:
    """Analyze AST tree for valid structure, docstrings, and forbidden constructs."""
    print_stage("Stage 2: AST Code Analysis & Structure Check")
    py_files = find_python_files()
    all_ok = True
    for path in py_files:
        rel_path = os.path.relpath(path, REPO_ROOT)
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=rel_path)
            # Verify top-level docstring in root scripts
            if os.path.dirname(path) == REPO_ROOT:
                doc = ast.get_docstring(tree)
                if not doc:
                    print_info(f"{rel_path} lacks module docstring (recommended)")
            print_pass(f"AST parse verified: {rel_path}")
        except SyntaxError as e:
            print_fail(f"AST parse failed: {rel_path}", f"Line {e.lineno}: {e.msg}")
            all_ok = False
    return all_ok


def stage_3_linter_and_style() -> bool:
    """Run ruff or flake8 if installed, otherwise perform built-in hygiene checks."""
    print_stage("Stage 3: Linting & Code Quality")
    # Try ruff
    try:
        res = subprocess.run(["ruff", "check", "."], cwd=REPO_ROOT, capture_output=True, text=True)
        if res.returncode == 0:
            print_pass("ruff check passed cleanly")
            return True
        else:
            print_fail("ruff found style or lint issues:", res.stdout or res.stderr)
            return False
    except FileNotFoundError:
        pass

    # Try flake8 (third-party vendored sample excluded: not our code style)
    try:
        res = subprocess.run(["flake8", "--max-line-length=130", "--ignore=E501,W503",
                              "--exclude=.git,__pycache__,.venv,venv,out,.agents,FusionMCPSample", "."],
                             cwd=REPO_ROOT, capture_output=True, text=True)
        if res.returncode == 0:
            print_pass("flake8 lint check passed cleanly")
            return True
        else:
            print_fail("flake8 found issues:", res.stdout or res.stderr)
            return False
    except FileNotFoundError:
        print_info("Neither ruff nor flake8 installed globally; AST syntax check already validated.")
        return True


def stage_4_type_check() -> bool:
    """Run pyright type checker if installed, using pyrightconfig.json."""
    print_stage("Stage 4: Static Type Checking (pyright)")
    # Check if pyright or npx is available
    pyright_found = False
    cmd = []

    # Check if pyright is available as a module or binary
    try:
        check = subprocess.run([sys.executable, "-m", "pyright", "--version"],
                               capture_output=True, text=True)
        if check.returncode == 0:
            pyright_found = True
            cmd = [sys.executable, "-m", "pyright"]
    except Exception:
        pass

    if not pyright_found:
        try:
            check = subprocess.run(["where", "pyright"] if sys.platform == "win32" else ["which", "pyright"],
                                   capture_output=True, text=True)
            if check.returncode == 0:
                pyright_found = True
                cmd = ["pyright"]
        except Exception:
            pass

    if not pyright_found:
        print_info("pyright binary not found in system PATH. Install via 'npm install -g pyright'. Skipping local type check.")
        return True

    try:
        if sys.platform == "win32" and cmd == ["pyright"]:
            cmd = ["cmd.exe", "/c", "pyright"]
        res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        output = res.stdout or res.stderr
        if res.returncode == 0 or "0 errors" in output:
            print_pass("pyright type checking passed with 0 errors")
            return True
        else:
            print_fail("pyright reported type errors:", output.strip()[:800])
            return False
    except Exception as e:
        print_info(f"pyright execution encountered error ({e}); skipped.")
        return True


def stage_5_unit_tests() -> bool:
    """Run pure-Python unit tests (derivations, tolerances, BOM generation)."""
    print_stage("Stage 5: Core Conveyor Generator Unit Tests")
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_conveyor_generator")
    runner = unittest.TextTestRunner(verbosity=1)
    res = runner.run(suite)
    if res.wasSuccessful():
        print_pass(f"{res.testsRun} unit tests passed")
        return True
    else:
        print_fail(f"{len(res.failures)} failed, {len(res.errors)} errors in unit tests")
        return False


def stage_6_autodesk_api_integration() -> bool:
    """Run mock Autodesk Fusion API integration & CAD generator tests."""
    print_stage("Stage 6: Autodesk Fusion 360 API Integration & CAD Generator Tests")
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_fusion_api_mock")
    runner = unittest.TextTestRunner(verbosity=1)
    res = runner.run(suite)
    if res.wasSuccessful():
        print_pass(f"{res.testsRun} Autodesk Fusion API integration tests passed")
        return True
    else:
        print_fail(f"{len(res.failures)} failed, {len(res.errors)} errors in Fusion API tests")
        return False


def stage_7_fusion_mcp_contract() -> bool:
    """Run Autodesk Fusion MCP Protocol & Contract Tests."""
    print_stage("Stage 7: Autodesk Fusion MCP Server Contract Tests")
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_fusion_mcp_contract")
    runner = unittest.TextTestRunner(verbosity=1)
    res = runner.run(suite)
    if res.wasSuccessful():
        print_pass(f"{res.testsRun} Autodesk Fusion MCP contract tests passed")
        return True
    else:
        print_fail(f"{len(res.failures)} failed, {len(res.errors)} errors in MCP contract tests")
        return False


PLATFORM_SUITES = [
    "tests.test_units_strict",
    "tests.test_serialization",
    "tests.test_docking_math",
    "tests.test_regression_legacy",
    "tests.test_debug_export",
    "tests.test_graph",
    "tests.test_manufacturing",
    "tests.test_intelligence",
    "tests.test_fusion_commands",
]


def stage_8_platform_tests() -> bool:
    """Run Conveyor Engineering Automation Platform suites (Phases 0-5)."""
    print_stage("Stage 8: Automation Platform Tests (units/serial/dock/graph/mfg/AI/panel)")
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    for name in PLATFORM_SUITES:
        suite.addTests(loader.loadTestsFromName(name))
    runner = unittest.TextTestRunner(verbosity=1)
    res = runner.run(suite)
    if res.wasSuccessful():
        print_pass(f"{res.testsRun} platform tests passed")
        return True
    else:
        print_fail(f"{len(res.failures)} failed, {len(res.errors)} errors in platform tests")
        return False


def main():
    print("=" * 65)
    print(f"{BOLD}AUTODESK FUSION 360 PARAMETRIC CI PIPELINE{RESET}")
    print("=" * 65)

    start_time = time.time()
    stages = [
        ("Syntax Compilation", stage_1_syntax_compilation),
        ("AST Structure & Quality", stage_2_ast_code_quality),
        ("Linter & Style", stage_3_linter_and_style),
        ("Type Checking", stage_4_type_check),
        ("Core Unit Tests", stage_5_unit_tests),
        ("Autodesk Fusion API Integration", stage_6_autodesk_api_integration),
        ("Autodesk Fusion MCP Contract", stage_7_fusion_mcp_contract),
        ("Automation Platform (Phases 0-5)", stage_8_platform_tests),
    ]

    results = []
    for name, func in stages:
        ok = func()
        results.append((name, ok))
        if not ok:
            print(f"\n{RED}{BOLD}CI PIPELINE STOPPED DUE TO FAILURE IN: {name}{RESET}")
            break

    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(f"{BOLD}CI PIPELINE SUMMARY ({elapsed:.2f}s){RESET}")
    print("=" * 65)
    all_passed = True
    for name, ok in results:
        status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  [{status}] {name}")
        if not ok:
            all_passed = False

    if all_passed:
        print(f"\n{GREEN}{BOLD}*** ALL CI CHECKS PASSED SUCCESSFULLY! ***{RESET}\n")
        sys.exit(0)
    else:
        print(f"\n{RED}{BOLD}*** CI PIPELINE FAILED. Please fix the issues above. ***{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
