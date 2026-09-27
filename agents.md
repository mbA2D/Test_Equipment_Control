# Agent instructions

- Always run this project's tests through the local virtual environment:
  `.\.venv\Scripts\python.exe -m pytest`.
- By default, use `.\.venv\Scripts\python.exe -m pytest -q` to reduce output and usage.
- Use `.\.venv\Scripts\python.exe -m pytest` when additional detail about a test run is needed.
- When referencing functions or specific code lines, use clickable file links with line numbers so their implementations can be opened directly.
- Prefer simple, concise, human-readable, and well-commented code. Changes should follow a well documented architecture plan.
- Do not patch bugs with workarounds or temporary fixes. Look for and identify the root cause to address the issue at the source.
