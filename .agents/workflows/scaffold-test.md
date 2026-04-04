# Test Scaffolding Workflow

When asked to scaffold tests for a specific file, follow these steps:

1. **Analyze:** Read the target Python file and identify all public classes and functions.
2. **Create File:** Generate a corresponding `test_<filename>.py` in the `tests/` directory.
3. **Scaffold:** Write `pytest` compatible boilerplate. Create a test class for every public class, and a test function for every public method.
4. **Asserts:** Include `assert False, "Test not implemented"` inside each function body so the test suite correctly reports them as pending tasks.
