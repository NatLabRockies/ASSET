# ==============================================
# Automated System-wide Strength Evaluation Tool (ASSET)
# Contributors: Pranav Sharma, Shahil Shah
# Last modified: 08/21/26
# Pranav Sharma and Shahil Shah, "Sizing and Placement of Grid Strengthening Devices Using Extra Element 
# Theorem," in IEEE Open Access Journal of Power and Energy, Sep. 2026, doi: 10.1109/OAJPE.2026.3732363.
# Pranav Sharma, Shahil Shah (2025), "Application of the Extra Element Theorem
# for Grid Strength Analysis in IBR-Dominated Systems", IEEE PES General Meeting.

#
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
import math

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
from psspy import _i, _f, _s
redirect.psse2py()

import numpy as np
import pandas as pd
import assetlib


# =============================================================================================
# Input parameters (test example defaults)
# =============================================================================================
working_dir = os.getcwd()
GUIinput_powerflowfile = working_dir + "\\input\\savnw.sav"  # Power flow file
GUIinput_poidata = working_dir + "\\input\\poidata.csv"  # POI data file
GUIinput_outputfolder = working_dir + "\\output"  # Output folder
GUIinput_contfolder = working_dir + "\\ctg"  # Contingency folder

GUIinput_DiscAllOwu = 1  # Include fault current contribution from IBR units? (0: No, 1: Yes)
GUIinput_SimMode = 0 # 0: Base SCR, 1: SCRIF, 2: Critical N-1/N-2 SCR, 3: Contingency scan
GUIinput_K = 10  # Fault current analysis depth (branches K-level away from tested POI)
GUIinput_SCRIF_DummyLoadMW = 25

# =============================================================================================
# Configuration parameters
# =============================================================================================
busNlimit = 50
ctg_num = 5


def _ensure_dirs():
    """Create output/temp folders and return the output folder path."""
    out_dir = GUIinput_outputfolder
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

    tmp_dir = os.path.join(working_dir, "temp")
    if not os.path.exists(tmp_dir):
        os.mkdir(tmp_dir)

    return out_dir


def _init_case(PFcase):
    """Initialize PSS/E and load the selected power-flow case."""
    psspy.psseinit(busNlimit)
    psspy.progress_output(6, "", [0, 0])
    psspy.alert_output(6, "", [0, 0])
    psspy.prompt_output(6, "", [0, 0])
    ierr = psspy.case(PFcase)
    if ierr != 0:
        raise Exception("SAV file cannot be opened.")


def _load_poi_inputs():
    """Load POI bus list and MW capacities from the configured CSV file."""
    POIdata = pd.read_csv(GUIinput_poidata)
    poi_list = POIdata['POI bus #'].values
    poi_pmax = POIdata['MW capacity'].values
    return poi_list, poi_pmax


def run_mode_base_scr(PFcase, poi_list, poi_pmax, out_dir):
    """Mode 0: compute base (N-0) SCMVA and SCR at each POI."""
    print("Mode 0 selected: Base SCR (N-0 only)")
    mode_suffix = "baseSCR"
    K = GUIinput_K
    Z9999_flag = GUIinput_DiscAllOwu

    SCMVA_POI = []
    SCR_POI = []

    for i, POIi in enumerate(poi_list):
        print("Processing POI %d/%d" % (i + 1, len(poi_list)))
        _init_case(PFcase)

        try:
            SCC_POI, SCC_kl, SCC_kl_array = assetlib.SC_k_lvl(psspy, POIi, K, poi_list, Z9999_flag)
        except ValueError as exc:
            print("Skipping POI %d: %s" % (POIi, exc))
            continue

        SCMVA_POI.append([int(SCC_POI[0]), SCC_POI[1]])
        SCR_POI.append([int(SCC_POI[0]), SCC_POI[1] / poi_pmax[i]])

    pd.DataFrame(SCMVA_POI, columns=['Bus number of POI', 'SCMVA(N-0)']).to_csv(
        os.path.join(out_dir, "result_SCMVA_" + mode_suffix + ".csv"), index=False)
    pd.DataFrame(SCR_POI, columns=['Bus number of POI', 'SCR(N-0)']).to_csv(
        os.path.join(out_dir, "result_SCR_" + mode_suffix + ".csv"), index=False)


def run_mode_scrif(PFcase, poi_list, poi_pmax, out_dir):
    """Mode 1: compute interaction-factor-based SCR (SCRIF)."""
    print("Mode 1 selected: Interaction factor based SCR (SCRIF)")
    K = GUIinput_K
    Z9999_flag = GUIinput_DiscAllOwu

    SCMVA_POI = []
    V_base = []
    valid_poi_indices = []

    for i in range(len(poi_list)):
        POIi = poi_list[i]
        print("Computing interaction factor for POI %d/%d" % (i + 1, len(poi_list)))
        _init_case(PFcase)

        try:
            SCC_POI, SCC_kl, SCC_kl_array = assetlib.SC_k_lvl(psspy, POIi, K, poi_list, Z9999_flag)
        except ValueError as exc:
            print("Skipping POI %d in SCRIF base case: %s" % (POIi, exc))
            continue

        SCMVA_POI.append([int(SCC_POI[0]), SCC_POI[1]])
        ierr, v = psspy.busdat(POIi, 'PU')
        if ierr != 0:
            raise Exception("Failed to get voltage for bus %d" % POIi)
        V_base.append(abs(v))
        valid_poi_indices.append(i)

    SCRIF_POI = []
    V_base = np.array(V_base)

    for valid_pos, i in enumerate(valid_poi_indices):
        POIi = poi_list[i]
        dummy_load = GUIinput_SCRIF_DummyLoadMW

        print("Computing SCRIF for POI %d/%d" % (valid_pos + 1, len(valid_poi_indices)))
        _init_case(PFcase)

        psspy.load_data_5(POIi, "TP", [_i, _i, _i, _i, _i, _i, _i], [_f, -dummy_load, _f, _f, _f, _f, _f, _f])
        psspy.fnsl([0, 0, 0, 0, 0, 1, 0, 0])

        V_del = []
        for poi_index in valid_poi_indices:
            POIj = poi_list[poi_index]
            ierr, v = psspy.busdat(POIj, 'PU')
            if ierr != 0:
                raise Exception("Failed to get voltage for bus %d" % POIj)
            V_del.append(abs(v))
        V_del = np.array(V_del)

        delta_i = abs(V_del[valid_pos] - V_base[valid_pos])
        Imp_Factor = []
        for j in range(len(valid_poi_indices)):
            if valid_pos == j:
                Imp_Factor.append(1.0)
            else:
                delta_j = abs(V_del[j] - V_base[j])
                IF = 0.0
                if delta_i > 1e-7:
                    IF = delta_j / delta_i
                    if IF < 1e-7:
                        IF = 0.0
                Imp_Factor.append(IF)

        psspy.purgload(POIi, "TP")
        psspy.fnsl([0, 0, 0, 0, 0, 1, 0, 0])

        denom = 0.0
        for j in range(len(valid_poi_indices)):
            denom += Imp_Factor[j] * poi_pmax[valid_poi_indices[j]]

        scrif = SCMVA_POI[valid_pos][1] / denom if denom > 0 else 0.0
        SCRIF_POI.append([SCMVA_POI[valid_pos][0], scrif])

    pd.DataFrame(SCMVA_POI, columns=['Bus number of POI', 'SCMVA(N-0)']).to_csv(
        os.path.join(out_dir, "result_SCMVA_SCRIF.csv"), index=False)
    pd.DataFrame(SCRIF_POI, columns=['Bus number of POI', 'SCRIF']).to_csv(
        os.path.join(out_dir, "result_SCRIF.csv"), index=False)


def run_mode_critical_n12(PFcase, poi_list, poi_pmax, out_dir):
    """Mode 2: compute SCR under critical N-1 and N-2 branch outages."""
    print("Mode 2 selected: SCR with Critical N-1/N-2")
    mode_suffix = "SCRN1N2"
    K = GUIinput_K
    Z9999_flag = GUIinput_DiscAllOwu

    SCMVA_POI = []
    sum_brch = []
    SCR_POI = []

    for i, POIi in enumerate(poi_list):
        print("Processing POI %d/%d" % (i + 1, len(poi_list)))
        _init_case(PFcase)

        try:
            SCC_POI, SCC_kl, SCC_kl_array = assetlib.SC_k_lvl(psspy, POIi, K, poi_list, Z9999_flag)
        except ValueError as exc:
            print("Skipping POI %d: %s" % (POIi, exc))
            continue

        try:
            SCC_ranking = np.flipud(np.argsort(SCC_kl_array[:, 2]))
            tp1, tp2 = assetlib.IdTop2Brch(PFcase, busNlimit, SCC_kl, SCC_kl_array, SCC_ranking)
            SCC_POIi_N1, SCC_POIi_N2 = assetlib.CalcSccN12(
                PFcase, busNlimit, POIi, SCC_kl, SCC_kl_array, tp1, tp2, poi_list, Z9999_flag
            )

            SCMVA_POI.append([int(SCC_POI[0]), SCC_POI[1], SCC_POIi_N1, SCC_POIi_N2])
            sum_brch.append([
                int(SCC_POI[0]),
                int(SCC_kl_array[tp1[0]][0]), int(SCC_kl_array[tp1[0]][1]), SCC_kl[tp1[0]][2],
                int(SCC_kl_array[tp2[0]][0]), int(SCC_kl_array[tp2[0]][1]), SCC_kl[tp2[0]][2]
            ])
            SCR_POI.append([
                int(SCC_POI[0]),
                SCC_POI[1] / poi_pmax[i],
                SCC_POIi_N1 / poi_pmax[i],
                SCC_POIi_N2 / poi_pmax[i]
            ])
        except Exception as exc:
            print("Skipping N-1/N-2 computation for POI %d: %s" % (POIi, exc))
            continue

    pd.DataFrame(SCMVA_POI, columns=['Bus number of POI', 'SCMVA(N-0)', 'SCMVA(N-1)', 'SCMVA(N-2)']).to_csv(
        os.path.join(out_dir, "result_SCMVA_" + mode_suffix + ".csv"), index=False)
    pd.DataFrame(sum_brch, columns=['Bus number of POI', 'From bus - Branch 1', 'To bus - Branch 1', 'ID - Branch 1',
                                    'From bus - Branch 2', 'To bus - Branch 2', 'ID - Branch 2']).to_csv(
        os.path.join(out_dir, "result_brch_" + mode_suffix + ".csv"), index=False)
    pd.DataFrame(SCR_POI, columns=['Bus number of POI', 'SCR(N-0)', 'SCR(N-1)', 'SCR(N-2)']).to_csv(
        os.path.join(out_dir, "result_SCR_" + mode_suffix + ".csv"), index=False)


def run_mode_contingency_scan(PFcase, poi_list, poi_pmax, out_dir):
    """Mode 3: compute SCR for predefined contingency sets from CSVs."""
    print("Mode 3 selected: Contingency scan")
    mode_suffix = "SCRContingency"

    ctg_branch = pd.read_csv(GUIinput_contfolder + "\\CTGs_branch.csv")
    ctg_3wind = pd.read_csv(GUIinput_contfolder + "\\CTGs_3wind.csv")
    ctg_gentrip = pd.read_csv(GUIinput_contfolder + "\\CTGs_gentrip.csv")
    ctg_discbus = pd.read_csv(GUIinput_contfolder + "\\CTGs_discbus.csv")
    ctg_clobranch = pd.read_csv(GUIinput_contfolder + "\\CTGs_clobranch.csv")

    res_df = pd.DataFrame({"POI": poi_list})
    poi_to_index = {}
    for idx, bus in enumerate(poi_list):
        poi_to_index[int(bus)] = idx

    print("Starting contingency SCR computation...")

    for ctgi in range(0, ctg_num + 1, 1):
        print("Contingency: " + str(ctgi))
        _init_case(PFcase)

        psspy.short_circuit_coordinates(ival=1)
        psspy.short_circuit_units(ival=1)

        scmva = []
        scr = []

        if ctgi == 0:
            psspy.bsys(sid=1, numbus=len(poi_list), buses=poi_list.tolist())
            results = pssarrays.iecs_currents(
                sid=1,
                all=0,
                flt3ph=1,
                fltlg=0,
                fltllg=0,
                fltll=0,
                fltloc=0,
                linout=0,
                linend=0,
                tpunty=0,
                lnchrg=1,
                shntop=1,
                dcload=0,
                zcorec=0,
                optnftrc=0,
                loadop=1,
                genxop=0,
                brktime=0.08333
            )
            for k in range(0, len(poi_list)):
                ierr, nomv = psspy.busdat(ibus=poi_list[k], string='BASE')
                scmva_k = abs(results.flt3ph[k].ia1) * nomv * math.sqrt(3) / 1000
                scmva.append(scmva_k)
                scr.append(scmva_k / poi_pmax[k])

            res_df['SCMVA_' + str(ctgi)] = scmva
            res_df['SCR_' + str(ctgi)] = scr
            continue

        tmp = ctg_branch[ctg_branch['CTG num'] == ctgi].reset_index(drop=True)
        for idx_tmp in range(len(tmp)):
            from_bus = tmp.loc[idx_tmp, 'From bus']
            to_bus = tmp.loc[idx_tmp, 'To bus']
            br_id = tmp.loc[idx_tmp, 'ID']
            ierr, v1 = psspy.busdat(ibus=from_bus, string='BASE')
            ierr, v2 = psspy.busdat(ibus=to_bus, string='BASE')
            if v1 == v2:
                psspy.branch_chng_3(
                    ibus=from_bus,
                    jbus=to_bus,
                    ckt=str(br_id),
                    intgar=[0, _i, _i, _i, _i, _i],
                    realar=[_f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f],
                    ratings=[_f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f],
                    namear=_s
                )
            else:
                psspy.two_winding_chng_5(
                    ibus=from_bus,
                    jbus=to_bus,
                    ckt=str(br_id),
                    intgar=[0, _i, _i, _i, _i, _i, _i, _i, _i, _i, _i, _i, _i, _i, _i],
                    realari=[_f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f],
                    ratings=[_f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f],
                    namear=_s,
                    vgrpar=_s
                )

        tmp = ctg_clobranch[ctg_clobranch['CTG num'] == ctgi].reset_index(drop=True)
        for idx_tmp in range(len(tmp)):
            from_bus = tmp.loc[idx_tmp, 'From bus']
            to_bus = tmp.loc[idx_tmp, 'To bus']
            br_id = tmp.loc[idx_tmp, 'ID']
            ierr, v1 = psspy.busdat(ibus=from_bus, string='BASE')
            ierr, v2 = psspy.busdat(ibus=to_bus, string='BASE')
            if v1 == v2:
                psspy.branch_chng_3(
                    ibus=from_bus,
                    jbus=to_bus,
                    ckt=str(br_id),
                    intgar=[1, _i, _i, _i, _i, _i],
                    realar=[_f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f],
                    ratings=[_f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f],
                    namear=_s
                )
            else:
                psspy.two_winding_chng_5(
                    ibus=from_bus,
                    jbus=to_bus,
                    ckt=str(br_id),
                    intgar=[1, _i, _i, _i, _i, _i, _i, _i, _i, _i, _i, _i, _i, _i, _i],
                    realari=[_f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f],
                    ratings=[_f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f],
                    namear=_s,
                    vgrpar=_s
                )

        tmp = ctg_3wind[ctg_3wind['CTG num'] == ctgi].reset_index(drop=True)
        for idx_tmp in range(len(tmp)):
            bus1 = tmp.loc[idx_tmp, 'From bus']
            bus2 = tmp.loc[idx_tmp, 'To bus 1']
            bus3 = tmp.loc[idx_tmp, 'To bus 2']
            br_id = tmp.loc[idx_tmp, 'ID']
            psspy.three_wnd_imped_chng_4(
                ibus=bus1,
                jbus=bus2,
                kbus=bus3,
                ckt=str(br_id),
                intgar=[_i, _i, _i, _i, _i, _i, _i, 0, _i, _i, _i, _i, _i],
                realari=[_f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f],
                namear=_s,
                vgrpar=_s
            )

        tmp = ctg_discbus[ctg_discbus['CTG num'] == ctgi].reset_index(drop=True)
        for idx_tmp in range(len(tmp)):
            bus = tmp.loc[idx_tmp, 'Bus']
            psspy.bus_chng_4(
                ibus=bus,
                inode=_i,
                intgar=[4, _i, _i, _i],
                realar=[_f, _f, _f, _f, _f, _f, _f],
                name=_s
            )

        tmp = ctg_gentrip[ctg_gentrip['CTG num'] == ctgi].reset_index(drop=True)
        for idx_tmp in range(len(tmp)):
            bus = tmp.loc[idx_tmp, 'Bus']
            geid = tmp.loc[idx_tmp, 'ID']
            psspy.machine_chng_2(
                ibus=bus,
                id=str(geid),
                intgar=[0, _i, _i, _i, _i, _i],
                realar=[_f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f, _f]
            )

        treeobj = psspy.treedat(sizeislands=_i)
        a = treeobj.get('island_busnum')
        islanded_buses = [element for inner_list in a for element in inner_list]
        psspy.island()

        poi_list_new = poi_list.copy()
        for bus_tmp in poi_list:
            if bus_tmp in islanded_buses:
                poi_list_new.remove(bus_tmp)

        psspy.bsys(sid=1, numbus=len(poi_list_new), buses=poi_list_new.tolist())
        results = pssarrays.iecs_currents(
            sid=1,
            all=0,
            flt3ph=1,
            fltlg=0,
            fltllg=0,
            fltll=0,
            fltloc=0,
            linout=0,
            linend=0,
            tpunty=0,
            lnchrg=1,
            shntop=1,
            dcload=0,
            zcorec=0,
            optnftrc=0,
            loadop=1,
            genxop=0,
            brktime=0.08333
        )

        bus_to_idx_new = {}
        for n2, poi_new in enumerate(poi_list_new):
            bus_to_idx_new[int(poi_new)] = n2

        for poi_old in poi_list:
            poi_old_int = int(poi_old)
            if poi_old_int in bus_to_idx_new:
                idxicc = bus_to_idx_new[poi_old_int]
                ierr, nomv = psspy.busdat(ibus=poi_old, string='BASE')
                scmva_old = abs(results.flt3ph[idxicc].ia1) * nomv * math.sqrt(3) / 1000
                scmva.append(scmva_old)
                scr.append(scmva_old / poi_pmax[poi_to_index[poi_old_int]])
            else:
                scmva.append(0.0)
                scr.append(0.0)

        res_df = pd.concat((res_df, pd.DataFrame({'SCMVA_' + str(ctgi): scmva})), axis=1)
        res_df = pd.concat((res_df, pd.DataFrame({'SCR_' + str(ctgi): scr})), axis=1)

    scmva_cols = ['POI'] + [col for col in res_df.columns if col.startswith('SCMVA_')]
    scr_cols = ['POI'] + [col for col in res_df.columns if col.startswith('SCR_')]

    res_df_scmva = res_df[scmva_cols]
    res_df_scr = res_df[scr_cols]

    res_df_scmva.to_csv(
        os.path.join(out_dir, 'result_SCMVA_' + mode_suffix + '.csv'),
        index=False
    )
    res_df_scr.to_csv(
        os.path.join(out_dir, 'result_SCR_' + mode_suffix + '.csv'),
        index=False
    )


def main():
    """Dispatch to the selected SCR analysis mode and write outputs."""
    out_dir = _ensure_dirs()
    PFcase = GUIinput_powerflowfile
    poi_list, poi_pmax = _load_poi_inputs()

    _init_case(PFcase)

    if GUIinput_SimMode == 0:
        run_mode_base_scr(PFcase, poi_list, poi_pmax, out_dir)
    elif GUIinput_SimMode == 1:
        run_mode_scrif(PFcase, poi_list, poi_pmax, out_dir)
    elif GUIinput_SimMode == 2:
        run_mode_critical_n12(PFcase, poi_list, poi_pmax, out_dir)
    elif GUIinput_SimMode == 3:
        run_mode_contingency_scan(PFcase, poi_list, poi_pmax, out_dir)
    else:
        raise ValueError("Unsupported GUIinput_SimMode: %s" % str(GUIinput_SimMode))

    print("Simulation complete.")


if __name__ == "__main__":
    main()
