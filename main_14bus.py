# ==============================================
# Automated System-wide Strength Evaluation Tool (ASSET) - EET Based Sensitivity Analysis
# Contributors: Pranav Sharma, Shahil Shah
# Last modified: 08/21/26
# Pranav Sharma and Shahil Shah, "Sizing and Placement of Grid Strengthening Devices Using Extra Element 
# Theorem," in IEEE Open Access Journal of Power and Energy, Sep. 2026, doi: 10.1109/OAJPE.2026.3732363.
# Pranav Sharma, Shahil Shah, "Application of the Extra Element Theorem
# for Grid Strength Analysis in IBR-Dominated Systems", IEEE PES General Meeting, Jul. 2025.

# ==============================================
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.widgets import Slider
from matplotlib.patches import Circle
import matplotlib.cm as cm
import matplotlib.colors as mcolors

# Auto-detect PSSE paths when available.
import pssepath
pssepath.add_pssepath()

import psse34
import psspy, excelpy, dyntools, redirect, pssarrays

redirect.psse2py()

import assetlib


working_dir = os.path.dirname(os.path.abspath(__file__))

# =============================================================================================
# Input Parameters
# =============================================================================================
GUIinput_powerflowfile = working_dir + "\\input\\ieee14bus.sav"
GUIinput_poidata = working_dir + "\\input\\poi_14bus.csv"
GUIinput_candidate = working_dir + "\\input\\candidate_14bus.csv"
GUIinput_outputfolder = working_dir + "\\output_14bus"

GUIinput_DiscAllOwu = 1
GUIinput_K = 10
GUIinput_Gm = 10000.0
GUIinput_Xsource = 1.0
GUIinput_SC_MachineID = "1"

busNlimit = 50


def _ensure_dirs():
    if not os.path.exists(GUIinput_outputfolder):
        os.mkdir(GUIinput_outputfolder)

    tmp_dir = os.path.join(working_dir, "temp")
    if not os.path.exists(tmp_dir):
        os.mkdir(tmp_dir)


def _build_positions(poi_ids, cand_ids):
    """Build bus marker positions with fixed anchors for 14-bus defaults and fallback grid."""
    positions = {}

    if len(poi_ids) >= 5 and len(cand_ids) >= 1:
        positions[int(poi_ids[0])] = (1000, 1850)
        positions[int(poi_ids[1])] = (2600, 1300)
        positions[int(poi_ids[2])] = (1100, 530)
        positions[int(poi_ids[3])] = (3000, 900)
        positions[int(poi_ids[4])] = (2050, 150)
        positions[int(cand_ids[0])] = (500, 1400)

    x_start, y_start = 600, 300
    x_step, y_step = 350, 280
    for idx, bus in enumerate(poi_ids):
        bus = int(bus)
        if bus not in positions:
            positions[bus] = (x_start + (idx % 5) * x_step, y_start + (idx // 5) * y_step)

    for idx, bus in enumerate(cand_ids):
        bus = int(bus)
        if bus not in positions:
            positions[bus] = (300, 1200 + idx * 80)

    return positions


def interactive_scr_map_plot(scr_base, s_k, s_k_i, poi_list, candidate_list, bus_positions, image_path):
    n_poi = len(poi_list)
    n_cand = len(candidate_list)
    g_k = np.zeros(n_cand)

    fig, ax = plt.subplots(figsize=(12, 8))
    plt.subplots_adjust(left=0.25, bottom=0.1 + 0.05 * max(1, n_cand))

    if os.path.exists(image_path):
        img = mpimg.imread(image_path)
        ax.imshow(img)
        ax.axis('off')
    else:
        print("Warning: background image not found at %s. Using blank canvas." % image_path)
        ax.set_facecolor('#f7f9fb')
        ax.grid(alpha=0.2)
        ax.set_title('SCR Map (No Background Image)')

    scr_norm = mcolors.Normalize(vmin=0, vmax=20)
    colormap = cm.get_cmap('RdYlGn')

    circle_artists = []
    scr_labels = []
    radius = 120

    for i in range(n_poi):
        bus_id = int(poi_list[i])
        x, y = bus_positions[bus_id]
        scr_val = float(scr_base[i])
        color = colormap(scr_norm(scr_val))
        circle = Circle((x, y), radius, facecolor=color, edgecolor='black', alpha=0.6)
        ax.add_patch(circle)
        circle_artists.append(circle)
        label = ax.text(x, y, "%.2f" % scr_val, color='black', fontsize=10, ha='center', va='center', fontweight='bold')
        scr_labels.append(label)

    hydro_text = None
    if len(candidate_list) > 0:
        hydro_bus = int(candidate_list[0])
        hx, hy = bus_positions[hydro_bus]
        hydro_text = ax.text(hx, hy - 20, "Online Hydro gen. = 330 MW", ha='center', color='blue', fontsize=10)

    sliders = []
    axcolor = 'lightgoldenrodyellow'
    for i in range(n_cand):
        ax_slider = plt.axes([0.25, 0.05 + i * 0.04, 0.65, 0.03], facecolor=axcolor)
        slider = Slider(
            ax_slider,
            'Change in Hydro capacity (%)',
            0,
            200,
            valinit=0,
            valstep=1,
            valfmt='%.0f%%'
        )
        sliders.append(slider)

    def update(_):
        for i, slider in enumerate(sliders):
            percent = slider.val / 100.0
            g_k[i] = (1.0 / 0.303) * 330.0 * percent

        numerator = 1.0 + np.sum(g_k / s_k)
        for i in range(n_poi):
            poi_id = int(poi_list[i])
            denom_terms = g_k / s_k_i[i]
            for k, candidate_id in enumerate(candidate_list):
                if int(candidate_id) == poi_id:
                    denom_terms[k] = 0.0
            denominator = 1.0 + np.sum(denom_terms)
            scr_new = scr_base[i] * (numerator / denominator)

            color = colormap(scr_norm(scr_new))
            circle_artists[i].set_facecolor(color)
            scr_labels[i].set_text("%.2f" % scr_new)

        if hydro_text is not None:
            hydro_text.set_text("Online Hydro gen. = %.0f MW" % (330.0 + (g_k[0] * 0.303)))

        fig.canvas.draw_idle()

    for slider in sliders:
        slider.on_changed(update)

    plt.show()


def main():
    """Run EET compute with current assetlib API and launch interactive SCR map."""
    _ensure_dirs()

    poi_df = pd.read_csv(GUIinput_poidata)
    cand_df = pd.read_csv(GUIinput_candidate)

    poi_list = poi_df['POI bus #'].values
    poi_pmax = poi_df['MW capacity'].values
    candidate_list = cand_df['Candidate bus #'].values

    print("Running EET workflow with current assetlib API...")
    results = assetlib.EET_compute(
        psspy_api=psspy,
        PFcase=GUIinput_powerflowfile,
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
    poi_ids = [int(v) for v in results['poi_ids']]
    cand_ids = [int(v) for v in results['cand_ids']]

    pmax_map = {int(poi_list[i]): float(poi_pmax[i]) for i in range(len(poi_list))}
    scr_rows = []
    for row in s_i0_rows:
        bus = int(row[0])
        s_i0 = float(row[1])
        pmax = pmax_map.get(bus, 0.0)
        if abs(pmax) < 1e-9:
            continue
        scr_rows.append([bus, s_i0 / pmax])

    pd.DataFrame(s_i0_rows, columns=['Bus number of POI', 'S_i0']).to_csv(
        os.path.join(GUIinput_outputfolder, 'result_S_i0.csv'), index=False)
    pd.DataFrame(scr_rows, columns=['Bus number of POI', 'SCR_i0']).to_csv(
        os.path.join(GUIinput_outputfolder, 'result_SCR_i0.csv'), index=False)
    pd.DataFrame(s_k0_rows, columns=['Bus number of Candidate Bus', 'S_k0']).to_csv(
        os.path.join(GUIinput_outputfolder, 'result_S_k0.csv'), index=False)

    if len(s_ki_rows) > 0:
        s_ki_df = pd.DataFrame(s_ki_rows, columns=['Candidate Bus', 'POI Bus', 'S_ki'])
        s_ki_df.pivot(index='Candidate Bus', columns='POI Bus', values='S_ki').to_csv(
            os.path.join(GUIinput_outputfolder, 'result_S_ki_matrix.csv'))

    epsilon = 1e-6
    scr_map = {int(v[0]): float(v[1]) for v in scr_rows}
    sk_map = {int(v[0]): float(v[1]) for v in s_k0_rows}

    scr_base = np.array([scr_map.get(int(p), np.nan) for p in poi_ids], dtype=float)
    valid_scr = np.isfinite(scr_base)
    if not np.any(valid_scr):
        print("No valid SCR values available for plotting.")
        return

    plot_poi_ids = [poi_ids[i] for i in range(len(poi_ids)) if valid_scr[i]]
    scr_base = scr_base[valid_scr]

    s_k = np.array([max(epsilon, sk_map.get(int(c), epsilon)) for c in cand_ids], dtype=float)

    poi_id_to_index = {int(bus): i for i, bus in enumerate(plot_poi_ids)}
    cand_id_to_index = {int(bus): i for i, bus in enumerate(cand_ids)}
    s_k_i = np.zeros((len(plot_poi_ids), len(cand_ids)), dtype=float)

    for row in s_ki_rows:
        c_bus = int(row[0])
        p_bus = int(row[1])
        val = float(row[2])
        if p_bus in poi_id_to_index and c_bus in cand_id_to_index:
            s_k_i[poi_id_to_index[p_bus], cand_id_to_index[c_bus]] = val

    s_k_i = np.where(np.isfinite(s_k_i) & (s_k_i != 0.0), s_k_i, epsilon)

    bus_positions = _build_positions(plot_poi_ids, cand_ids)
    image_path = os.path.join(working_dir, 'bus14v2.png')

    print("Launching interactive map plot...")
    interactive_scr_map_plot(
        scr_base=scr_base,
        s_k=s_k,
        s_k_i=s_k_i,
        poi_list=plot_poi_ids,
        candidate_list=cand_ids,
        bus_positions=bus_positions,
        image_path=image_path,
    )


if __name__ == "__main__":
    main()
