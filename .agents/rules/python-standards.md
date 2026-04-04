# Python Engineering Standards

When writing or modifying Python code in this repository, strictly adhere to the following standards:

- **Modern Syntax:** Target Python 3.8+. Use f-strings for formatting and the `typing` module for all function signatures and complex variables.
- **Class Structure:** Use modern class definitions (`class Parser:` instead of `class Parser(object):`).
- **Data Structures:** Prefer `@dataclass` for pure data models over standard classes or named tuples.
- **Modularity:** Keep functions small and single-purpose. Do not mix I/O or UI rendering logic with core parsing or business logic.
- **Dependencies:** Standard library only unless otherwise specified.
- **Linting:** Code must be PEP 8 compliant.
