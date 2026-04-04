# Objective
Perform a full architectural refactor of the abandoneed 'googler' project, forked and now renamed on github & future debian packaging'googler-ng', and for python/pip 'googler_ng' transitioning it from a monolithic single-file python script 'googler.py' to a modern, modular Python package. The goal is to improve maintainability, testability, and resilience to Google's layout changes.

# Project Overview
Googler-ng is a CLI tool for Google Search/News/Videos. It fetches HTML (to avoid API limits), parses it using a custom embedded DOM engine, and provides both a direct CLI and an interactive REPL.

# Strict Agent Instruction 
**DO NOT write programmatic scripts (e.g., `split_googler.py`) using AST or Regex to perform this refactor.** You must act as a direct file editor. Manually extract the requested classes/functions, create the target files, and paste the code. Execute ONLY the specific Phase requested by the user, update the checkboxes to `[x]`, and then proceed to the next stage.

# Refactoring Strategy
Please split the code into the following package structure under a new `googler_ng/` directory:

- googler_ng/core/:
   - `url.py`: URL construction logic (`GoogleUrl`).
   - `connection.py`: HTTP/HTTPS handling and TLS optimizations (`HardenedHTTPSConnection` and `GoogleConnection`).
- googler_ng/dom/:
   - `engine.py` (or `__init__.py`): Isolate the entire embedded `dim` DOM/CSS engine here. Since it's a completely standalone generic implementation, it should not be conflated with the Google parser logic.
- googler_ng/parser/:
   - `models.py`: Pure data structures for `Result` and `Sitelink`.
   - `google.py`: The `GoogleParser` class. 
- googler_ng/config/:
   - `selectors.py` (or JSON): Isolate the configuration maps for CSS selectors. Instead of hardcoding classes like `div.yuRUbf` in the parser methods, abstract these out to configuration files to allow for rapid updates when Google changes its layout.
- googler_ng/ui/:
   - `repl.py`: The interactive `GooglerCmd` (REPL) logic.
   - `cli.py`: Argument parsing (`GooglerArgumentParser`) and the main logic runner.
   - `printer.py` / `colors.py`: Output formatting, terminal escape sequences, `COLORMAP`, and UI display logic. 
- googler_ng/utils/:
   - `helpers.py`: Utility functions (`open_url`, `unwrap_link`).
   - `text.py`: Text formatting wrappers such as `TrackedTextwrap` and the monkeypatch logic.
Note: no self-upgrade logic is required

# Key Requirements
- **Modernization:** Use Python 3.8+ features (Type Hinting, f-strings, and `class Name:` instead of `class Name(object):`, and standard dataclasses for `Result`/`Sitelink`).
- **Decoupling:** Ensure the Parser does not know about the UI (no print statements or UI colors inside parser), and the UI only interacts with the Parser through the core models.
- **Entry Points:** - Create a `__main__.py` in the root of the `googler_ng/` package so the tool can be run as `python3 -m googler_ng`.
   - Ensure the root directory still contains a lightweight `googler` executable wrapper for backward compatibility for developers and simple script downloads.
- **Packaging:** Generate a `pyproject.toml` with `[project.scripts]` entry points to handle the new package structure effectively, providing a standard PIP-installable distribution.

**Current detailed instructions are in tasks.md for you to keep updated after every stage**
