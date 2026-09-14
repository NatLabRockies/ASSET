# ==============================================
# Automated System-wide Strength Evaluation Tool (ASSET) - EET Based Sensitivity Analysis
# Contributors: Pranav Sharma, Shahil Shah
# Last modified: 08/21/26
# Pranav Sharma and Shahil Shah, "Sizing and Placement of Grid Strengthening Devices Using Extra Element 
# Theorem," in IEEE Open Access Journal of Power and Energy, Sep. 2026, doi: 10.1109/OAJPE.2026.3732363.
# Pranav Sharma, Shahil Shah, "Application of the Extra Element Theorem
# for Grid Strength Analysis in IBR-Dominated Systems", IEEE PES General Meeting, Jul. 2025.
# ==============================================

# Copyright (c) 2026 Alliance for Energy Innovation, LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# ==============================================

import os
import sys
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

# =============================================================================================
# Setting the PSS/E installation folders
# =============================================================================================
PSSE_Path = r"C:\Program Files (x86)\PTI\PSSE34\PSSBIN"
PSSPY_Path = r"C:\Program Files (x86)\PTI\PSSE34\PSSPY37"

sys.path.append(PSSE_Path)
os.environ['PATH'] += ";" + PSSE_Path
sys.path.append(PSSPY_Path)
os.environ['Path'] += ";" + PSSPY_Path

# =============================================================================================
# Load and initialize the PSS/E API
# =============================================================================================
import psse34
import psspy, excelpy, dyntools, redirect, pssarrays
redirect.psse2py()

import assetlib
from offtheshlef_optimization import run_gsd_sizing


# =============================================================================================
# Inputs (test system defaults)
# =============================================================================================
working_dir = os.path.dirname(os.path.abspath(__file__))
GUIinput_powerflowfile = working_dir + "\\input\\savnw.sav"
GUIinput_poidata = working_dir + "\\input\\poidata.csv"
GUIinput_candidate = working_dir + "\\input\\candidate.csv"
GUIinput_outputfolder = working_dir + "\\output_EET"

GUIinput_DiscAllOwu = 1 #IBR Contribution 
GUIinput_K = 10 #How far to look 
GUIinput_Gm = 10000.0 # A GSD device connected to compute the base case. 
GUIinput_Xsource = 1.0 #
GUIinput_SC_MachineID = "1"
GUIinput_TargetSCR = 3.0
GUIinput_EET_Mode = 3  # 1: sensitivity, 2: sensitivity + GSD sizing, 3: sensitivity + manual interactive GSD tuning

busNlimit = 50


def _ensure_dirs():
    """Create output and temp folders when missing."""
    if not os.path.exists(GUIinput_outputfolder):
        os.mkdir(GUIinput_outputfolder)

    tmp_dir = os.path.join(working_dir, "temp")
    if not os.path.exists(tmp_dir):
        os.mkdir(tmp_dir)


def _load_inputs():
    """Load POI and candidate input tables from CSV files."""
    poi_df = pd.read_csv(GUIinput_poidata)
    cand_df = pd.read_csv(GUIinput_candidate)
    poi_list = poi_df['POI bus #'].values
    poi_pmax = poi_df['MW capacity'].values
    candidate_list = cand_df['Candidate bus #'].values
    return poi_list, poi_pmax, candidate_list


def _compute_scr_rows(s_i0_rows, poi_pmax, poi_order):
    """Convert base short-circuit strengths (S_i0) into SCR_i0 rows."""
    pmax_map = {}
    for idx, bus in enumerate(poi_order):
        pmax_map[int(bus)] = float(poi_pmax[idx])

    scr_rows = []
    for bus, s_i0 in s_i0_rows:
        pmax = pmax_map.get(int(bus), 0.0)
        if abs(pmax) < 1e-9:
            scr = np.nan
        else:
            scr = float(s_i0) / pmax
        scr_rows.append([int(bus), scr])
    return scr_rows


def _report_scr_threshold_status(scr_rows, target_scr):
    """Print a concise SCR-threshold summary and return counts.

    Returns:
        (num_below, num_valid)
    """
    scr_values = np.array([float(v[1]) for v in scr_rows], dtype=float)
    valid_mask = np.isfinite(scr_values)
    num_valid = int(np.sum(valid_mask))

    if num_valid == 0:
        print("No valid SCR_i0 values are available for threshold screening.")
        return 0, 0

    num_below = int(np.sum(scr_values[valid_mask] < float(target_scr)))
    print("%d out of %d POIs have SCR less than the target threshold (%.2f)." %
          (num_below, num_valid, float(target_scr)))

    if num_below == 0:
        print("All POIs have SCR above the threshold; no additional grid strengthening devices are needed.")

    return num_below, num_valid


def _save_sensitivity_heatmap(sens_df, out_dir, out_name='sensitivity_heatmap.png'):
    # Hide the self-coupling diagonal (value 1.0) for a cleaner visual.
    mask = sens_df == 1.0

    n_rows, n_cols = sens_df.shape
    show_annotations = (n_rows <= 30 and n_cols <= 30)
    xtick_step = 1 if n_cols <= 30 else (5 if n_cols <= 100 else 10)
    ytick_step = 1 if n_rows <= 30 else (5 if n_rows <= 100 else 10)
    fig_w = min(30, max(10, 0.35 * n_cols))
    fig_h = min(28, max(8, 0.30 * n_rows))

    plt.figure(figsize=(fig_w, fig_h))
    sns.heatmap(
        sens_df,
        cmap="Greens",
        annot=show_annotations,
        fmt=".2f",
        linewidths=0.3,
        mask=mask,
        xticklabels=xtick_step,
        yticklabels=ytick_step,
        cbar_kws={"shrink": 0.8}
    )
    plt.xlabel("Candidate bus")
    plt.ylabel("POI bus")
    plt.title("Sensitivity Heatmap")

    heatmap_path = os.path.join(out_dir, out_name)
    plt.savefig(heatmap_path, dpi=300, bbox_inches='tight')
    plt.close('all')


def _transform_gamma_for_plot(gamma_df):
    """Prepare gamma for visualization using log1p and percentile clipping.

    gamma can be very large or inf. We clip positive finite values at high percentile,
    map +inf to the clip value, then apply log1p for readable scaling.
    """
    arr = gamma_df.to_numpy(dtype=float)
    pos_finite = arr[np.isfinite(arr) & (arr >= 0.0)]

    if pos_finite.size == 0:
        clip_val = 1.0
    else:
        clip_val = float(np.nanpercentile(pos_finite, 99.0))
        clip_val = max(clip_val, 1.0)

    arr_plot = np.array(arr, dtype=float)
    arr_plot = np.where(np.isposinf(arr_plot), clip_val, arr_plot)
    arr_plot = np.where(np.isneginf(arr_plot), np.nan, arr_plot)
    arr_plot = np.where(arr_plot < 0.0, np.nan, arr_plot)
    arr_plot = np.where(np.isfinite(arr_plot), np.minimum(arr_plot, clip_val), np.nan)

    log_arr = np.log1p(arr_plot)
    return pd.DataFrame(log_arr, index=gamma_df.index, columns=gamma_df.columns), clip_val


def _save_gamma_heatmap(gamma_df, out_dir, out_name='gamma_heatmap_log1p.png'):
    gamma_log_df, clip_val = _transform_gamma_for_plot(gamma_df)

    n_rows, n_cols = gamma_log_df.shape
    show_annotations = (n_rows <= 30 and n_cols <= 30)
    xtick_step = 1 if n_cols <= 30 else (5 if n_cols <= 100 else 10)
    ytick_step = 1 if n_rows <= 30 else (5 if n_rows <= 100 else 10)
    fig_w = min(30, max(10, 0.35 * n_cols))
    fig_h = min(28, max(8, 0.30 * n_rows))

    plt.figure(figsize=(fig_w, fig_h))
    ax = sns.heatmap(
        gamma_log_df,
        cmap="YlOrRd",
        annot=show_annotations,
        fmt=".2f",
        linewidths=0.3,
        xticklabels=xtick_step,
        yticklabels=ytick_step,
        cbar_kws={"shrink": 0.8}
    )
    ax.set_xlabel("Candidate bus")
    ax.set_ylabel("POI bus")
    ax.set_title("Gamma Heatmap (log1p, clipped at 99th percentile)")

    heatmap_path = os.path.join(out_dir, out_name)
    plt.savefig(heatmap_path, dpi=300, bbox_inches='tight')
    plt.close('all')


def _build_ski_matrix_from_rows(s_ki_rows, poi_ids, cand_ids):
    poi_map = {int(bus): i for i, bus in enumerate(poi_ids)}
    cand_map = {int(bus): k for k, bus in enumerate(cand_ids)}

    ski = np.full((len(poi_ids), len(cand_ids)), np.nan)
    for row in s_ki_rows:
        c_bus = int(row[0])
        p_bus = int(row[1])
        val = float(row[2])
        if p_bus in poi_map and c_bus in cand_map:
            ski[poi_map[p_bus], cand_map[c_bus]] = val
    return ski


def _compute_scr_from_gsd(g_vec, scr_base_vec, s_k_vec, s_ki_mat):
    eps = 1e-9
    sk = np.array(s_k_vec, dtype=float)
    ski = np.array(s_ki_mat, dtype=float)

    sk = np.where(~np.isfinite(sk) | (np.abs(sk) < eps), eps, sk)
    ski = np.where(~np.isfinite(ski) | (np.abs(ski) < eps), eps, ski)

    numerator = 1.0 + np.sum(g_vec / sk)
    scr_new = np.zeros(len(scr_base_vec), dtype=float)
    for i in range(len(scr_base_vec)):
        denominator = 1.0 + np.sum(g_vec / ski[i, :])
        scr_new[i] = scr_base_vec[i] * (numerator / denominator)
    return scr_new


def _run_manual_interactive_visualization(scr_rows, s_k0_rows, s_ki_rows, poi_ids, cand_ids, target_scr, out_dir):
    if len(poi_ids) == 0 or len(cand_ids) == 0:
        print("Manual visualization skipped: POI or candidate list is empty.")
        return

    scr_map = {int(v[0]): float(v[1]) for v in scr_rows if np.isfinite(v[1])}
    sk_map = {int(v[0]): float(v[1]) for v in s_k0_rows if np.isfinite(v[1])}

    scr_base = np.array([scr_map.get(int(p), np.nan) for p in poi_ids], dtype=float)
    sk_vec = np.array([sk_map.get(int(c), np.nan) for c in cand_ids], dtype=float)
    ski_mat = _build_ski_matrix_from_rows(s_ki_rows, poi_ids, cand_ids)

    valid_scr_idx = np.where(np.isfinite(scr_base))[0]
    if len(valid_scr_idx) == 0:
        print("Manual visualization skipped: no finite SCR_i0 values found.")
        return

    if len(valid_scr_idx) < len(scr_base):
        print("Warning: some POIs have invalid SCR_i0 and will be excluded from interactive visualization.")

    plot_poi_ids = [int(poi_ids[i]) for i in valid_scr_idx]
    scr_base_plot = scr_base[valid_scr_idx]
    ski_plot = ski_mat[valid_scr_idx, :]

    eps = 1e-9
    sk_safe = np.where(~np.isfinite(sk_vec) | (np.abs(sk_vec) < eps), eps, sk_vec)
    ski_safe = np.where(~np.isfinite(ski_plot) | (np.abs(ski_plot) < eps), eps, ski_plot)

    finite_sk = sk_safe[np.isfinite(sk_safe) & (sk_safe > 0.0)]
    if finite_sk.size == 0:
        gsd_max = 500.0
    else:
        gsd_max = max(500.0, float(np.nanpercentile(finite_sk, 75)))

    g_vec = np.zeros(len(cand_ids), dtype=float)

    n_poi = len(plot_poi_ids)
    n_cand = len(cand_ids)
    fig_h = min(28.0, max(8.0, 4.5 + 0.32 * n_cand))

    fig, ax = plt.subplots(figsize=(14, fig_h))

    # Reserve a dedicated lower band for sliders so POI tick labels stay visible.
    slider_step = 0.024
    slider_height = 0.015
    slider_bottom_start = 0.06
    slider_top = slider_bottom_start + slider_step * max(0, n_cand - 1) + slider_height
    plot_bottom = min(0.86, slider_top + 0.10)
    plt.subplots_adjust(left=0.10, right=0.98, bottom=plot_bottom, top=0.92)

    x = np.arange(n_poi)
    width = 0.38

    scr_new = _compute_scr_from_gsd(g_vec, scr_base_plot, sk_safe, ski_safe)
    bars_base = ax.bar(x - width / 2.0, scr_base_plot, width=width, label='Base SCR', color='#6c8ebf')
    bars_new = ax.bar(x + width / 2.0, scr_new, width=width, label='Post-GSD SCR', color='#8fbc8f')
    ax.axhline(target_scr, color='crimson', linestyle='--', linewidth=1.2, label='Target SCR')

    ax.set_xticks(x)
    ax.set_xticklabels([str(v) for v in plot_poi_ids], rotation=45, ha='right')
    ax.set_xlabel('POI bus')
    ax.set_ylabel('SCR')
    ax.set_title('Interactive Grid Strength Device Tuning: SCR Improvement by POI')
    y_top = max(float(np.nanmax(scr_base_plot)) * 1.4, target_scr * 1.3, 1.0)
    ax.set_ylim(0.0, y_top)
    ax.legend(loc='upper left')

    fig.text(0.02, slider_top + 0.006, 'Candidate bus', fontsize=10, weight='bold')
    fig.text(0.50, max(0.01, slider_bottom_start - 0.028), 'GSD Size in MVA', ha='center', fontsize=10)

    sliders = []
    for i, cand_bus in enumerate(cand_ids):
        y_pos = slider_bottom_start + slider_step * (n_cand - 1 - i)
        axis = plt.axes([0.12, y_pos, 0.80, slider_height])
        slider = Slider(axis, str(int(cand_bus)), 0.0, gsd_max, valinit=0.0)
        sliders.append(slider)

    def _update(_):
        for i, slider in enumerate(sliders):
            g_vec[i] = float(slider.val)

        new_vals = _compute_scr_from_gsd(g_vec, scr_base_plot, sk_safe, ski_safe)
        for i, bar in enumerate(bars_new):
            bar.set_height(new_vals[i])

        min_scr = float(np.nanmin(new_vals)) if new_vals.size > 0 else np.nan
        total_g = float(np.sum(g_vec))
        ax.set_title('Interactive Grid Strength Device Tuning: min SCR=%.3f, total G=%.2f MVA' % (min_scr, total_g))

        current_top = max(float(np.nanmax(np.concatenate([scr_base_plot, new_vals]))) * 1.15, target_scr * 1.3, 1.0)
        ax.set_ylim(0.0, current_top)
        fig.canvas.draw_idle()

    for slider in sliders:
        slider.on_changed(_update)

    plt.show()

    final_g = np.array([float(slider.val) for slider in sliders], dtype=float)
    final_scr = _compute_scr_from_gsd(final_g, scr_base_plot, sk_safe, ski_safe)

    pd.DataFrame({
        'Candidate Bus': [int(c) for c in cand_ids],
        'G_manual': final_g,
    }).to_csv(os.path.join(out_dir, 'result_GSD_manual_values.csv'), index=False)

    pd.DataFrame({
        'POI Bus': plot_poi_ids,
        'SCR_i0': scr_base_plot,
        'SCR_manual': final_scr,
        'SCR_improvement': final_scr - scr_base_plot,
    }).to_csv(os.path.join(out_dir, 'result_SCR_manual_comparison.csv'), index=False)

    plt.figure(figsize=(12, 6))
    plt.plot(plot_poi_ids, scr_base_plot, marker='o', label='Base SCR', color='#6c8ebf')
    plt.plot(plot_poi_ids, final_scr, marker='s', label='Manual Post-GSD SCR', color='#8fbc8f')
    plt.axhline(target_scr, color='crimson', linestyle='--', linewidth=1.2, label='Target SCR')
    plt.xlabel('POI bus')
    plt.ylabel('SCR')
    plt.title('Manual GSD Tuning Result (After Closing Interactive Window)')
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'manual_gsd_scr_comparison.png'), dpi=300)
    plt.close('all')

    print('Manual interactive visualization complete.')
    print('Saved: result_GSD_manual_values.csv, result_SCR_manual_comparison.csv, manual_gsd_scr_comparison.png')


def _stage1_closure_check(s_i0_rows, s_k0_rows, s_ki_rows, sens_mat, poi_ids, cand_ids):
    """Validate Stage-1 outputs before sizing optimization."""
    issues = []

    if len(s_i0_rows) == 0:
        issues.append("No S_i0 rows were computed.")
    if len(s_k0_rows) == 0:
        issues.append("No S_k0 rows were computed.")
    if len(s_ki_rows) == 0:
        issues.append("No S_ki rows were computed.")
    if sens_mat is None:
        issues.append("Sensitivity matrix is missing.")
    else:
        if sens_mat.shape != (len(poi_ids), len(cand_ids)):
            issues.append("Sensitivity matrix dimensions do not match POI/candidate sets.")

    if len(s_i0_rows) > 0 and not np.all(np.isfinite(np.array([v[1] for v in s_i0_rows], dtype=float))):
        issues.append("S_i0 contains non-finite values.")
    if len(s_k0_rows) > 0 and not np.all(np.isfinite(np.array([v[1] for v in s_k0_rows], dtype=float))):
        issues.append("S_k0 contains non-finite values.")

    if len(issues) == 0:
        print("Stage 1 closure check passed: S_i0/S_k0/S_ki/sensitivity are ready.")
        return True

    print("Stage 1 closure check failed. Skipping optimization.")
    for msg in issues:
        print(" - %s" % msg)
    return False


def main():
    """Run the EET pipeline and optionally launch sizing/tuning workflows."""
    _ensure_dirs()
    print("Output folder:", GUIinput_outputfolder)
    eet_mode = max(1, int(GUIinput_EET_Mode))

    PFcase = GUIinput_powerflowfile
    poi_list, poi_pmax, candidate_list = _load_inputs()

    try:
        print("Extra element theorem based grid strength studies and sizing of grid strengthening devices (GSDs) starting...")
        results = assetlib.EET_compute(
            psspy_api=psspy,
            PFcase=PFcase,
            poi_list=poi_list,
            candidate_list=candidate_list,
            busNlimit=busNlimit,
            Z9999_flag=GUIinput_DiscAllOwu,
            K=GUIinput_K,
            Gm=GUIinput_Gm,
            xsource=GUIinput_Xsource,
            sc_machine_id=GUIinput_SC_MachineID,
            base_dir=working_dir,
        )

        s_i0_rows = results['s_i0_rows']
        s_k0_rows = results['s_k0_rows']
        s_ki_rows = results['s_ki_rows']
        poi_ids = results['poi_ids']
        cand_ids = results['cand_ids']
        sens_mat = results['sens_mat']
        gamma_mat = results['gamma_mat']
        scr_rows = _compute_scr_rows(s_i0_rows, poi_pmax, poi_list)

        pd.DataFrame(s_i0_rows, columns=['Bus number of POI', 'S_i0']).to_csv(
            os.path.join(GUIinput_outputfolder, 'result_S_i0.csv'), index=False)
        pd.DataFrame(scr_rows, columns=['Bus number of POI', 'SCR_i0']).to_csv(
            os.path.join(GUIinput_outputfolder, 'result_SCR_i0.csv'), index=False)
        pd.DataFrame(s_k0_rows, columns=['Bus number of Candidate Bus', 'S_k0']).to_csv(
            os.path.join(GUIinput_outputfolder, 'result_S_k0.csv'), index=False)

        if len(s_ki_rows) > 0:
            s_ki_df = pd.DataFrame(s_ki_rows, columns=['Candidate Bus', 'POI Bus', 'S_ki'])
            s_ki_matrix = s_ki_df.pivot(index='Candidate Bus', columns='POI Bus', values='S_ki')
            s_ki_matrix.to_csv(os.path.join(GUIinput_outputfolder, 'result_S_ki_matrix.csv'))

        sens_df = pd.DataFrame(sens_mat, index=poi_ids, columns=cand_ids)
        sens_df.to_csv(os.path.join(GUIinput_outputfolder, 'result_Sensitivity.csv'))
        _save_sensitivity_heatmap(sens_df, GUIinput_outputfolder)

        gamma_df = pd.DataFrame(gamma_mat, index=poi_ids, columns=cand_ids)
        gamma_df.to_csv(os.path.join(GUIinput_outputfolder, 'result_Gamma_max_improvement.csv'))
        _save_gamma_heatmap(gamma_df, GUIinput_outputfolder)

        stage1_ready = _stage1_closure_check(
            s_i0_rows=s_i0_rows,
            s_k0_rows=s_k0_rows,
            s_ki_rows=s_ki_rows,
            sens_mat=sens_mat,
            poi_ids=poi_ids,
            cand_ids=cand_ids,
        )

        num_below, num_valid = (0, 0)
        if stage1_ready:
            num_below, num_valid = _report_scr_threshold_status(scr_rows, GUIinput_TargetSCR)

        if eet_mode == 2 and stage1_ready:
            if num_valid == 0:
                print("Optimization skipped because SCR threshold screening has no valid POI values.")
            elif num_below == 0:
                print("Optimization skipped because all POIs already satisfy the SCR threshold.")
            else:
                print("Optimizing Grid Strengthening Device (GSD) allocation")
                sizing_rows = run_gsd_sizing(
                    scr_rows=scr_rows,
                    s_k0_rows=s_k0_rows,
                    s_ki_rows=s_ki_rows,
                    poi_ids=poi_ids,
                    cand_ids=cand_ids,
                    target_scr=GUIinput_TargetSCR,
                )
                if len(sizing_rows) > 0:
                    pd.DataFrame(
                        sizing_rows,
                        columns=['Candidate Bus', 'G_opt']
                    ).to_csv(os.path.join(GUIinput_outputfolder, 'result_GSD_sizing.csv'), index=False)
            print("Sensitivity + GSD sizing complete.")
        elif eet_mode == 3 and stage1_ready:
            print("Starting manual interactive GSD tuning visualization.")
            _run_manual_interactive_visualization(
                scr_rows=scr_rows,
                s_k0_rows=s_k0_rows,
                s_ki_rows=s_ki_rows,
                poi_ids=poi_ids,
                cand_ids=cand_ids,
                target_scr=GUIinput_TargetSCR,
                out_dir=GUIinput_outputfolder,
            )
            print("Sensitivity + manual interactive tuning complete.")
        elif eet_mode >= 2:
            print("Sensitivity complete. Optimization was not started because Stage 1 did not close cleanly.")
        else:
            print("Sensitivity complete.")

        print("Outputs written: result_S_i0.csv, result_SCR_i0.csv, result_S_k0.csv, result_S_ki_matrix.csv, result_Sensitivity.csv, sensitivity_heatmap.png, result_Gamma_max_improvement.csv, gamma_heatmap_log1p.png")
    except ValueError as exc:
        print(str(exc))


if __name__ == '__main__':
    main()
