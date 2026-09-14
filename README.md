# Automated System-wide Strength Evaluation Tool (ASSET)

ASSET is a Python + PSS/E workflow for grid-strength analysis at points of interconnection (POIs). The current repository has been streamlined to focus on two production analysis paths:

- SCR-focused analysis modes in `main.py`
- EET-based sensitivity, manual tuning, and optimization in `EET_implementation.py`

## Current Repository Structure

Core files:

- `main.py`
	- Unified SCR workflow with four analysis modes.
- `EET_implementation.py`
	- EET workflow for sensitivity, manual interactive GSD tuning, and optional optimization.
- `assetlib.py`
	- Core computation library (short-circuit parsing, N-1/N-2 helpers, EET core matrix build and derivatives).
- `offtheshlef_optimization.py`
	- Off-the-shelf optimization routines used by EET mode 2.

Support folders:

- `input/` for case and CSV inputs
- `ctg/` for contingency definitions
- `output/` and `output_EET/` for generated results
- `pssepath/` for local path helper utilities

## Capabilities

### 1) SCR workflow (`main.py`)

`main.py` supports four modes via `GUIinput_SimMode`:

- `0`: Base SCR (N-0)
- `1`: SCRIF (interaction-factor-based SCR)
- `2`: Critical N-1/N-2 SCR
- `3`: Contingency scan from `ctg/*.csv`

Typical outputs include mode-specific SCR and SCMVA CSV files in `output/`.

### 2) EET workflow (`EET_implementation.py`)

`EET_implementation.py` supports three modes via `GUIinput_EET_Mode`:

- `1`: Sensitivity and gamma outputs
- `2`: Sensitivity + optimization-based GSD sizing
- `3`: Sensitivity + manual interactive GSD tuning (slider UI)

Typical outputs are written to `output_EET/`, including:

- `result_S_i0.csv`
- `result_SCR_i0.csv`
- `result_S_k0.csv`
- `result_S_ki_matrix.csv`
- `result_Sensitivity.csv`
- `result_Gamma_max_improvement.csv`
- `sensitivity_heatmap.png`
- `gamma_heatmap_log1p.png`
- (mode 2) `result_GSD_sizing.csv`
- (mode 3) `result_GSD_manual_values.csv`, `result_SCR_manual_comparison.csv`, `manual_gsd_scr_comparison.png`

## Requirements

- Windows environment with PSS/E installed and licensed
- Python environment compatible with your PSS/E install
- Installed modules used by the scripts:
	- `numpy`
	- `pandas`
	- `matplotlib`
	- `seaborn`
	- `scipy` (required for optimization mode)

Notes:

- The scripts currently use explicit PSS/E paths in code.
- Verify `PSSE_Path` and `PSSPY_Path` variables in `main.py`, `EET_implementation.py`, and `assetlib.py` for your machine.

## How to Run

### Run SCR workflow

1. Configure paths and mode in `main.py`:
	 - `GUIinput_powerflowfile`
	 - `GUIinput_poidata`
	 - `GUIinput_outputfolder`
	 - `GUIinput_contfolder` (for mode 3)
	 - `GUIinput_SimMode`
2. Execute:

```bash
python main.py
```

### Run EET workflow

1. Configure paths and mode in `EET_implementation.py`:
	 - `GUIinput_powerflowfile`
	 - `GUIinput_poidata`
	 - `GUIinput_candidate`
	 - `GUIinput_outputfolder`
	 - `GUIinput_EET_Mode`
2. Execute:

```bash
python EET_implementation.py
```

## Input Data Expectations

The workflows assume CSV inputs with repository-style columns.

At minimum:

- POI data contains `POI bus #` and `MW capacity`
- Candidate data contains `Candidate bus #`

For contingency mode, the `ctg/` folder should contain compatible contingency definition CSV files.

## Citation

If you use ASSET in publications, cite:

```text
Pranav Sharma and Shahil Shah, "Sizing and Placement of Grid Strengthening Devices Using Extra Element Theorem," in IEEE Open Access Journal of Power and Energy, Sep. 2026, doi: 10.1109/OAJPE.2026.3732363.

Pranav Sharma, Shahil Shah, "Application of the Extra Element Theorem for Grid Strength Analysis in IBR-Dominated Systems", 2025 IEEE Power & Energy Society General Meeting (PESGM), Austin, Texas, USA, 2025.

# ==============================================
```

## License

This codebase is distributed under the permissive license text included at the top of core source files.

Copyright (c) 2026 Alliance for Energy Innovation, LLC.

## Contact

For questions and collaboration inquiries:

- shahil.shah@nlr.gov
