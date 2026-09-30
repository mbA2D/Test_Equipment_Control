# Linux Control Computer Deployment

This guide records the staged source deployment for the Debian 13 x86_64
control computers. It keeps Debian's system Python intact and runs the app
from a project-local Python 3.14 virtual environment.

## Prepare Debian and install Git

Perform system package updates only while the computer is idle and outside a
battery test. Review the available changes before accepting the upgrade:

```bash
sudo apt update
apt list --upgradable
sudo apt upgrade
```

Install Git and the available downloader/certificate tools if they are not
already present:

```bash
sudo apt install -y git wget ca-certificates
git --version
```

`apt upgrade` is for routine updates within the installed Debian release. Do
not change Debian releases as part of this procedure. If a kernel is upgraded,
schedule a reboot during maintenance before the computer is commissioned.

## Clone the application

Run commands as the normal application account, not as root. Install Git first
if needed, then clone the published application branch:

```bash
mkdir -p ~/apps
cd ~/apps
git clone --branch python-3.14 --single-branch \
  https://github.com/mbA2D/Test_Equipment_Control.git
cd Test_Equipment_Control
```

Install uv for that account. Debian images may have `wget` instead of `curl`:

```bash
wget -qO- https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

Create the project environment from the repository's `.python-version` pin and
install the hardware and analysis extras:

```bash
uv python install 3.14.7
uv venv --python 3.14.7 .venv
uv pip install --python .venv/bin/python -e '.[hardware,analysis]'
```

The `hardware` extra installs PyVISA-related transports and USB/serial/GPIB
packages. The `analysis` extra installs BDF helpers. `dev` is not needed to run
the app. Install OS packages only when a required native driver or device
permission is identified.

## Verify the environment

```bash
.venv/bin/python --version
uv pip check --python .venv/bin/python
.venv/bin/battery-cycle --help
```

The project interpreter should report Python 3.14.7. Debian's `/usr/bin/python3`
remains managed by Debian and may report a different version. Do not replace it
or change `update-alternatives` for this application.

## Current commissioning record

On 2026-09-29, `battery-rack-top` was checked out on branch `python-3.14` at
commit `e068a2f`. The APT history confirms `apt upgrade` completed and
`apt install -y git` installed Git 2.47.3. The upgrade installed kernel
6.12.111. The computer was rebooted and verified running kernel 6.12.111. The
recommended `apt update` command is included above, but its execution is not
separately recorded in APT history.

uv installed Python 3.14.7 for the application account, and the project `.venv`
was created with the `hardware` and `analysis` extras. The environment
contains 66 packages and `uv pip check` reports no dependency conflicts.
Debian's system Python remains 3.13.5. Git and wget are available on the host.

At initial commissioning, the `battery-cycle` entry point needed
`PYTHONPATH=.` because the editable install omitted standalone modules such as
`Templates`. Commit `c826287` added those runtime modules to the setuptools
package configuration. After reinstalling that revision, the CLI works
without `PYTHONPATH`, including when started outside the source checkout.

On 2026-09-29 local time, a full CLI simulation completed with exit code 0. It
ran charge, rest, discharge, and rest steps using only the built-in fake PSU,
fake electronic load, and fake DMMs, with `SIMULATED_LG_MJ1` as the cell model.
It wrote one 14-row BDF CSV and its metadata sidecar under
`/home/a2dbatterylab/battery_test_runs/CLI_SIM_20260930T025957Z/output/`.
The metadata status is `completed` and records simulated equipment serials.
The invocation used `PYTHONPATH=.` for the editable-install issue above. No
physical instrument discovery, instrument communication, or battery-cell run
has been commissioned on this computer.

On 2026-09-29 local time, `battery-rack-bottom` (`192.168.5.251`) was updated
and rebooted. APT history confirms `apt upgrade` completed and Git 2.47.3 was
installed. The host is running kernel `6.12.111`. The `python-3.14` branch was
checked out at the same `e068a2f` commit used on the top computer. `uv` 0.12.21
installed Python 3.14.7, and the project `.venv` was created with the
`hardware` and `analysis` extras. It contains 66 packages and `uv pip check`
reports no dependency conflicts. Debian's system Python remains 3.13.5.

A full CLI simulation completed with exit code 0 using fake equipment and
`SIMULATED_LG_MJ1`. It wrote a 45-row BDF CSV, metadata sidecar, and completed
cell manifest under
`/home/a2dbatterylab/battery_test_runs/CLI_SIM_BOTTOM_20260929/output/`.
The BDF contains `CC_CHG`, `REST`, `CC_DCH`, and `REST` step labels, and the
metadata records the fake equipment model and serial numbers. The 10 ms sample
interval produced one 2.8 ms overrun. As on the top computer, the CLI was run
with `PYTHONPATH=.`. Linux instrument discovery and supervised physical
hardware validation have not been performed.

On 2026-09-30, both computers were advanced to commit `c826287` and their
project environments were reinstalled in editable mode. `uv pip check` passed
on both. From `/tmp` with `PYTHONPATH` unset, each installation's
`battery-cycle --help` worked. The bottom computer also completed a four-step fake
equipment run through the editable install with exit code 0. Its BDF metadata
reports `completed`, the expected `CC_CHG`, `REST`, `CC_DCH`, and `REST` labels,
and simulated instrument model and serial numbers. The output is under
`/home/a2dbatterylab/battery_test_runs/CLI_SIM_BOTTOM_EDITABLE_20260930/output/`.

The two rack checkouts received commit `c826287` through a local Git bundle.
The `python-3.14` branch was published with that fix on 2026-09-30, so a fresh
clone includes the corrected package configuration.

## Operational boundary

Dependency installation only prepares the software environment. Before using
real equipment, separately verify Linux USB/serial/GPIB access, VISA resource
discovery, instrument identification and safe output state, then complete a
supervised simulated run and a supervised hardware validation. Do not run
package upgrades or reboot while a battery test is active.
