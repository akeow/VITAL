# VITAL: Vessel Integrated Turbine Assessment for LCOE

VITAL is an open-source Python package for screening-level assessment of tidal energy systems integrated with vessels, floating platforms, or other deployable marine-energy infrastructure.

The software combines tidal resource data, rotor performance information, vessel or platform assumptions, dynamic rotor simulation, physical constraint checks, cost models, annual energy production, and Levelized Cost of Energy (LCOE) calculations.

VITAL supports representative workflows for:

- battery-charging applications,
- grid-connected applications,
- design-variable grid-search optimization,
- and early-stage comparison of candidate sites and system assumptions.

Results are intended for early-stage screening and comparison. They should not be interpreted as final engineering, permitting, or deployment recommendations.

## Documentation

The documentation is available at:

<https://sandialabs.github.io/VITAL/>

The documentation includes:

- a quickstart tutorial,
- module-specific tutorials,
- case studies,
- assumptions and FAQ,
- and API documentation.

## Prerequisites

Install Conda or Miniconda before creating the VITAL environment.

- Anaconda: <https://www.anaconda.com/download>
- Miniconda: <https://docs.conda.io/en/latest/miniconda.html>

For users new to Conda, the Anaconda and Miniconda documentation provide installation and getting-started resources.

## Installation

### 1. Clone the repository

<!-- NOTE: Code block starts below. Keep the opening and closing triple backticks. -->

```bash
git clone https://github.com/sandialabs/VITAL.git
cd VITAL
```

<!-- NOTE: Code block ended above. -->

### 2. Create the Conda environment

```bash
conda env create --file environment.yml
```

### 3. Activate the environment

```bash
conda activate VITAL_env
```

### 4. Install VITAL in editable mode

```bash
pip install -e .
```

For development and documentation dependencies, use:

```bash
pip install -e ".[dev]"
```

## Running the tutorials

After installing VITAL, launch Jupyter Notebook or JupyterLab:

```bash
jupyter notebook
```

or:

```bash
jupyter lab
```

Then open the notebooks in the `example/` directory.

Recommended learning path:

1. `01_quickstart.ipynb`
2. `02_tidaldata.ipynb`
3. `03_rotordata.ipynb`
4. `04_rotor_simulation.ipynb`
5. `05_constraint_checking.ipynb`
6. `06_lcoe_calculation.ipynb`
7. `07_optimization.ipynb`
8. `08_loss_models.ipynb`

Case studies are also provided in the `example/` directory.

## Building the documentation locally

From the repository root:

```bash
conda activate VITAL_env
cd docs
make clean
make html
```

The built documentation will be available at:

```text
docs/build/index.html
```

On macOS, open it with:

```bash
open build/index.html
```

## Managing the Conda environment

Deactivate the environment:

```bash
conda deactivate
```

Remove the environment:

```bash
conda env remove --name VITAL_env
```

## License

Copyright 2025 National Technology & Engineering Solutions of Sandia, LLC (NTESS).

Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights in this software.

This project is licensed under the Apache License, Version 2.0. See `LICENSE.md` for details.

Third-party license notices are provided in the `LICENSE/` directory.