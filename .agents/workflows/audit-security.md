# Security Audit Workflow

When instructed to run the security audit workflow, execute the following steps sequentially:

1. **Static Analysis:** Scan the repository for common anti-patterns (e.g., hardcoded credentials, unsafe `eval()` calls, or `shell=True` in subprocesses).
2. **Dependency Check:** Review `pyproject.toml` or `requirements.txt` for outdated or notoriously vulnerable packages.
3. **Report Generation:** Create a `security_audit.md` file in the root directory detailing any findings, categorized by severity (Critical, High, Medium, Low), along with suggested remediations.
4. **Halt:** Do not attempt to fix the vulnerabilities automatically unless explicitly instructed.
