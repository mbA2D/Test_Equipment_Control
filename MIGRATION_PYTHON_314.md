# Python 3.14 Migration Plan

> Target date: 2026-09-16  
> Current Python: 3.9.10  
> Primary target: Python 3.14  
> Fallback target: Python 3.13  
> Status: Ready to execute

## 1. Summary

This repository will be migrated to **Python 3.14** in stages. The migration is not a single dependency bump because the code is currently tightly coupled to old Python, old pandas behavior, loose packaging, GUI prompts, multiprocessing, and real hardware.

The core dependency stack is installable on Python 3.14 on Windows. Optional hardware dependencies still need separate validation because they are not part of the primary battery-testing application.

The migration will use this order:

1. Snapshot the repository.
2. Remove or isolate obsolete code that cannot be maintained.
3. Fix Python-version and dependency-sensitive code.
4. Add modern packaging.
5. Install Python 3.14.
6. Install updated dependencies.
7. Validate imports, GUI startup, fake-equipment tests, and simulated battery tests.
8. Revalidate optional hardware separately.

No live lab hardware should be connected until the simulated end-to-end tests pass.

---

## 2. Current state

### Python and packaging

- Python 3.9.10 is currently installed.
- Python 3.14 is not installed.
- Dependencies are pinned in `requirements.txt`.
- The project has no `pyproject.toml`.
- `lab_equipment/` has no explicit `__init__.py`.
- Imports rely on running from the repository root.
- `.gitignore` currently ignores only `*.pyc` and `venv/`.

### Known migration-sensitive code

- `GraphIV.py:128` uses `df_charge.append(...)`.
- `GraphIV.py:344` uses `dict_dataframe.append(...)`.
- `DataFrame.append()` is removed in modern pandas.
- `GraphIV.py:138-209` contains obsolete triple-quoted ICA code.
- `live_graph_temp.py` fails to parse.
- `equipment.py` has duplicate `get_equipment_dict()` definitions.
- `lab_equipment/A2D_DAQ_control.py` has duplicate `A2D_DAQ.__del__()` definitions.
- Several scripts execute immediately on import and lack main guards.

### Dead or isolated code

- `live_graph_temp.py` is broken and mostly a placeholder.
- `lab_equipment/DMM_VIRTUAL.py` and `lab_equipment/DMM_FET_BOARD_EQ.py` are not part of the active core path.
- Some legacy scripts under `test_scripts/` are not pytest-compatible.

---

## 3. Dependency readiness

The following core packages were checked for Python 3.14 compatibility using pip wheel resolution on Windows:

| Package | Python 3.14 status | Resolved version |
|---|---:|---:|
| PyQt6 | ✅ installable | 6.11.0 |
| PyQt6-Qt6 | ✅ installable | 6.11.2 |
| PyQt6-sip | ✅ installable | 13.12.0 |
| pyqtgraph | ✅ installable | 0.14.0 |
| NumPy | ✅ installable | 2.5.3 |
| pandas | ✅ installable | 3.0.5 |
| SciPy | ✅ installable | 1.18.1 |
| matplotlib | ✅ installable | 3.11.2 |
| PyVISA | ✅ installable | 1.16.2 |
| PyVISA-py | ✅ installable | 0.8.1 |
| EasyGUI | ✅ installable | 0.98.3 |
| hidapi | ✅ installable | 0.15.0 |
| PyUSB | ✅ installable | 1.3.1 |
| PySerial | ✅ installable | 3.5 |
| DiffCapAnalyzer | ✅ installable | 0.1.1 |

Interpretation:

- “Installable” means compatible wheels were resolved for Python 3.14.
- Runtime compatibility still needs to be validated inside the application.
- Optional hardware dependencies should be validated separately and should not block the main migration.

Dependencies to remove or defer:

- `tk==0.1.0` is suspicious and likely unrelated to Python's built-in `tkinter`.
- `keyboard` should be optional.
- `retry` should be evaluated before inclusion.
- Transitive dependencies such as `pyparsing` should not be pinned directly unless required.

---

## 4. Migration strategy

The migration will preserve the current architecture while modernizing the runtime.

Core application scope:

- `battery_test.py`
- `charge_discharge_control.py`
- `equipment.py`
- `lab_equipment/`
- `Templates.py`
- `jsonIO.py`
- `FileIO.py`
- `GraphIV.py`
- `PlotTemps.py`
- `voltage_to_temp.py`

Deferred scope:

- Arduino I/O module
- Hardware smoke tests requiring physical instruments

The GUI, multiprocessing, and instrument-process architecture should remain intact during the dependency migration. Refactoring can happen later after simulated tests exist.

---

## 5. Execution checklist

### Phase 0 — Safety snapshot

- [ ] Review `git status`.
- [ ] Commit existing documentation.
- [ ] Create a migration branch:
  ```powershell
  git switch -c python-3.14
  ```
- [ ] Confirm no lab instrument is connected.
- [ ] Do not modify hardware behavior until simulated tests exist.

### Phase 1 — Code hygiene before dependency upgrade

- [ ] Remove or fix `live_graph_temp.py`.
- [ ] Remove duplicate `get_equipment_dict()` definition in `equipment.py`.
- [ ] Remove duplicate `A2D_DAQ.__del__()` definition in `lab_equipment/A2D_DAQ_control.py`.
- [ ] Remove the obsolete triple-quoted ICA block from `GraphIV.py`.
- [ ] Remove obviously unused imports.
- [ ] Add `if __name__ == "__main__":` guards to standalone scripts that currently execute on import.
- [ ] Update `.gitignore` to ignore new virtual environments:
  ```gitignore
  .venv*/
  venv/
  __pycache__/
  *.pyc
  ```
- [ ] Run syntax/import checks on Python 3.9.
- [ ] Commit this cleanup separately from the Python 3.14 dependency change.

### Phase 2 — Fix dependency-sensitive code

- [ ] Replace `GraphIV.py:128`:
  ```python
  df_ica = df_charge.append(df_discharge, ignore_index=True)
  ```
  with:
  ```python
  df_ica = pd.concat([df_charge, df_discharge], ignore_index=True)
  ```
- [ ] Replace `GraphIV.py:344`:
  ```python
  dict_dataframe = dataframe_csv.append(dict_dataframe)
  ```
  with:
  ```python
  dict_dataframe = pd.concat([dict_dataframe, dataframe_csv], ignore_index=True)
  ```
- [ ] Verify DataFrame column order and index behavior after the concat changes.
- [ ] Search for other deprecated pandas patterns.
- [ ] Confirm all instrument drivers import without side effects.
- [ ] Confirm all multiprocessing entry points are guarded by `if __name__ == "__main__":`.

### Phase 3 — Add modern packaging

- [ ] Create `pyproject.toml`.
- [ ] Add core runtime dependencies.
- [ ] Add optional hardware dependencies.
- [ ] Add optional analysis dependencies.
- [ ] Add development/test dependencies.
- [ ] Add package metadata.
- [ ] Add explicit package discovery configuration.
- [ ] Add `lab_equipment/__init__.py`.
- [ ] Do not move files during the first migration unless necessary.
- [ ] Keep the current script-based entry points working.

Suggested extras:

```toml
[project.optional-dependencies]
hardware = [
  "pyserial>=3.5,<4",
  "pyusb>=1.3,<2",
  "hidapi>=0.15,<1",
]
analysis = [
  "DiffCapAnalyzer>=0.1.1,<0.2",
]
dev = [
  "pytest>=8",
  "pytest-qt>=4",
  "ruff>=0.8",
  "mypy>=1.13",
]
```

Core runtime dependencies should include at least:

```toml
dependencies = [
  "PyQt6>=6.11,<7",
  "pyqtgraph>=0.14,<1",
  "numpy>=2.5,<3",
  "pandas>=3.0,<4",
  "scipy>=1.18,<2",
  "matplotlib>=3.11,<4",
  "PyVISA>=1.16,<2",
  "PyVISA-py>=0.8,<0.9",
  "easygui>=0.98.3,<1",
]
```

### Phase 4 — Install Python 3.14

- [ ] Install Python 3.14 from python.org or using the system package manager.
- [ ] Do not uninstall Python 3.9 yet.
- [ ] Verify installed interpreters:
  ```powershell
  py -0p
  ```
- [ ] Verify Python 3.14:
  ```powershell
  py -3.14 --version
  ```
- [ ] Create a dedicated virtual environment:
  ```powershell
  py -3.14 -m venv .venv314
  .\.venv314\Scripts\Activate.ps1
  ```
- [ ] Upgrade packaging tools:
  ```powershell
  python -m pip install --upgrade pip setuptools wheel
  ```
- [ ] Verify active interpreter:
  ```powershell
  python --version
  python -c "import sys; print(sys.executable)"
  ```

### Phase 5 — Install updated dependencies

- [ ] Install core dependencies.
- [ ] Install optional hardware dependencies only if needed for early smoke testing.
- [ ] Install development/test dependencies.
- [ ] Run dependency consistency check:
  ```powershell
  python -m pip check
  ```
- [ ] Freeze the environment for the migration record:
  ```powershell
  python -m pip freeze > requirements-py314.lock.txt
  ```

### Phase 6 — Import and syntax validation

- [ ] Run Python syntax compilation:
  ```powershell
  python -m compileall -q .
  ```
- [ ] Run dependency consistency:
  ```powershell
  python -m pip check
  ```
- [ ] Import the core modules:
  ```powershell
  python -c "import battery_test"
  python -c "import charge_discharge_control"
  python -c "import equipment"
  python -c "import Templates"
  python -c "import jsonIO"
  python -c "import FileIO"
  python -c "import GraphIV"
  ```
- [ ] Import representative drivers:
  ```powershell
  python -c "from lab_equipment import PyVisaDeviceTemplate"
  python -c "from lab_equipment import DMM_A2D_4CH_Isolated_ADC"
  python -c "from lab_equipment import Eload_DL3000"
  python -c "from lab_equipment import PSU_SPD1000"
  ```
- [ ] Resolve all import failures before GUI testing.

### Phase 7 — GUI and fake-equipment smoke test

- [ ] Run the main GUI using Python 3.14:
  ```powershell
  python battery_test.py
  ```
- [ ] Use only Fake Test equipment.
- [ ] Create one battery channel.
- [ ] Assign:
  - Fake Test PSU
  - Fake Test E-load
  - Fake Test DMM
- [ ] Start a short test.
- [ ] Stop the test.
- [ ] Verify CSV logs are created.
- [ ] Verify the GUI closes cleanly without orphan processes.

### Phase 8 — Automated test foundation

- [ ] Add `pytest`.
- [ ] Add `pytest-qt`.
- [ ] Add a fake PyVISA resource abstraction.
- [ ] Add fake PSU, e-load, DMM, and relay-board interfaces.
- [ ] Add a deterministic battery-cell world model.
- [ ] Add unit tests for cycle settings and safety conditions.
- [ ] Add unit tests for pandas data processing.
- [ ] Add queue/proxy tests for `VirtualDeviceTemplate`.
- [ ] Add a headless end-to-end test.
- [ ] Add a GUI smoke test using `pytest-qt`.

### Phase 9 — Optional hardware validation

Only after simulated tests pass:

- [ ] Install optional hardware dependencies.
- [ ] Validate PyVISA backends:
  ```powershell
  python -m visa info
  ```
- [ ] Connect one instrument at a time.
- [ ] Verify IDN and basic measurement.
- [ ] Verify output on/off behavior.
- [ ] Verify voltage/current measurement.
- [ ] Run hardware smoke tests only after explicit confirmation.

### Phase 10 ? Finalize

- [ ] Update README installation instructions.
- [ ] Replace Python 3.9 instructions with Python 3.14 instructions.
- [ ] Document how to create the virtual environment.
- [ ] Document fake-equipment testing.
- [ ] Document how to run tests.
- [ ] Remove old `requirements.txt` only after the new workflow is confirmed.
- [ ] Commit the final migration.
- [ ] Tag or merge the migration branch.

---

## 6. Validation gates

Do not proceed to the next phase until the current phase passes.

### Gate 1 — Clean baseline

Required:

- Repository is committed.
- No unexplained modified files.
- Known broken files are removed or fixed.

### Gate 2 — Code hygiene

Required:

- Duplicate definitions removed.
- Deprecated pandas calls fixed.
- Dead code removed or explicitly deferred.
- All scripts intended to run have main guards.

### Gate 3 — Python 3.14 environment

Required:

- `python --version` reports 3.14.x.
- `pip check` passes.
- Core imports succeed.

### Gate 4 — GUI smoke test

Required:

- GUI starts.
- Fake equipment can be assigned.
- A short test starts and stops.
- Logs are created.
- No orphan processes remain.

### Gate 5 — Automated tests

Required:

- Core unit tests pass.
- Queue/proxy tests pass.
- Simulated end-to-end battery test passes.

### Gate 6 — Hardware readiness

Required before using real lab hardware:

- Simulated tests pass.
- One instrument is verified at a time.
- Output control is validated at low energy.
- Safety limits are confirmed.

---

## 7. Rollback strategy

If Python 3.14 migration fails:

1. Keep Python 3.9 installed.
2. Keep the original `requirements.txt`.
3. Use the `python-3.14` branch for experimental work.
4. Return to `master` for normal lab work.
5. If a specific dependency blocks Python 3.14, try Python 3.13 instead.

---

## 8. Definition of done

The migration is complete when:

- Python 3.14 is the documented primary runtime.
- Core dependencies install cleanly.
- `pip check` passes.
- Syntax and imports pass.
- Fake-equipment GUI smoke test passes.
- Simulated end-to-end battery test passes.
- No duplicate or broken legacy files block maintenance.
- Packaging is modern and reproducible.
- Optional hardware paths are isolated.
- README instructions are updated.
