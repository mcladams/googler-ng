# CLAUDE.md - AI Developer Guide for gs-cli (googler-ng)

## Project Overview
`googler-ng` (Next Generation) is a command-line tool for Google Search (web, news, videos). 
**Important Architectural Shift:** This project was originally a legacy, monolithic single-file script (`googler`). It is currently being refactored into a modern, modular Python package under the `googler_ng/` directory using Python 3.8+ standards.

## Code Architecture (Target State)
The monolithic script is being split into the following modular package structure:

* **`googler_ng/core/`**: Network connection (`GoogleConnection`) and URL construction (`GoogleUrl`).
* **`googler_ng/dom/`**: The standalone, custom HTML/CSS parsing engine (`dim`). Completely decoupled from Google-specific logic.
* **`googler_ng/parser/`**: Google-specific HTML parsing (`GoogleParser`) and pure data models (`Result`, `Sitelink`).
* **`googler_ng/config/`**: CSS selectors and configuration constants.
* **`googler_ng/ui/`**: CLI argument parsing (`cli.py`), terminal styling (`colors.py`), and the interactive omniprompt (`repl.py`).
* **`googler_ng/utils/`**: Helper functions, text wrapping for CJK characters, and clipboard integrations.

## Development Commands
```bash
# Install locally in editable mode
pip install -e .

# Run the refactored package directly
python3 -m googler_ng [options] [keywords]
