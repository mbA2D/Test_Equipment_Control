# Python 3.14 Runtime

> Status date: 2026-09-25
> Supported runtime: Python 3.14.7
> Status: Core migration, packaging, deterministic simulation, and headless end-to-end validation complete; physical-hardware validation remains

## Runtime policy

Python 3.14.7 is the only supported Python version for this repository. The version is pinned in
`.python-version` and enforced by `pyproject.toml`. Python 3.9 and Python 3.13 are not supported
fallback runtimes.

The project uses `pyproject.toml` as the dependency and packaging source of truth. The generated
`requirements.lock.txt` file records the validated environment and should be regenerated when
dependencies change.

## Installation

From the repository root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[hardware,analysis,dev]"
```

Verify the environment:

```powershell
python --version
python -m pip check
python -m pytest
```

## Completed migration work

- Removed obsolete and syntax-broken legacy modules.
- Removed duplicate definitions and obsolete pandas code.
- Replaced dynamic `eval()` device dispatch with an allowlisted proxy-method registry.
- Added `pyproject.toml`, explicit package metadata, and `lab_equipment/__init__.py`.
- Updated the runtime dependency set for Python 3.14.
- Moved documentation into `docs/`.
- Moved manually invoked instrument scripts into `hardware_tests/`.
- Added an initial unit/import/GUI smoke-test suite under `tests/`.

## Remaining validation

- Validate real multiprocessing, GUI, VISA, serial, USB, and HID behavior on
  the target lab workstation. The automated suite covers simulated process,
  GUI-component, and headless end-to-end paths, but not physical hardware.
- Run hardware scripts from `hardware_tests/` only with connected equipment and explicit operator approval.

## Supported commands

Start the GUI:

```powershell
.\.venv\Scripts\python.exe battery_test.py
```

Run automated tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run a hardware script manually, for example:

```powershell
.\.venv\Scripts\python.exe hardware_tests/test_A2D_Eload.py
```
