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

import numpy as np

try:
    from scipy.optimize import minimize, Bounds, NonlinearConstraint, linprog
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False


def _build_matrix(entry_list, row_ids, col_ids):
    """Build a dense [POI x Candidate] matrix from long-form triplets."""
    row_map = {int(rid): idx for idx, rid in enumerate(row_ids)}
    col_map = {int(cid): idx for idx, cid in enumerate(col_ids)}

    mat = np.full((len(row_ids), len(col_ids)), np.nan)
    for entry in entry_list:
        c_bus = int(entry[0])
        p_bus = int(entry[1])
        val = float(entry[2])
        if p_bus in row_map and c_bus in col_map:
            mat[row_map[p_bus], col_map[c_bus]] = val
    return mat


def run_gsd_sizing(scr_rows, s_k0_rows, s_ki_rows, poi_ids, cand_ids, target_scr):
    """Solve continuous GSD sizing to enforce a minimum SCR target."""
    if not SCIPY_AVAILABLE:
        print("SciPy not available; skipping sizing optimization.")
        return []

    scr_map = {int(v[0]): float(v[1]) for v in scr_rows if not np.isnan(v[1])}
    sk_map = {int(v[0]): float(v[1]) for v in s_k0_rows}

    scr_base_vec = np.array([scr_map.get(int(p), np.nan) for p in poi_ids], dtype=float)
    sk_vec = np.array([sk_map.get(int(c), np.nan) for c in cand_ids], dtype=float)
    ski_mat = _build_matrix(s_ki_rows, poi_ids, cand_ids)

    valid_idx = np.where(~np.isnan(scr_base_vec))[0]
    if len(valid_idx) == 0:
        print("No valid SCR_i0 values available for sizing optimization.")
        return []

    # Candidate buses without valid S_k cannot participate in optimization.
    valid_cand_idx = np.where(~np.isnan(sk_vec))[0]
    if len(valid_cand_idx) == 0:
        print("No valid S_k0 values available for candidate buses; skipping sizing optimization.")
        return []

    cand_ids_used = [int(cand_ids[k]) for k in valid_cand_idx]
    sk_vec = sk_vec[valid_cand_idx]
    ski_mat = ski_mat[:, valid_cand_idx]

    idx_target = valid_idx[scr_base_vec[valid_idx] < target_scr]
    if len(idx_target) == 0:
        print("All POIs already meet target SCR %.2f." % target_scr)
        return []

    scr_base_sub = scr_base_vec[idx_target]
    ski_sub = ski_mat[idx_target, :]

    eps = 1e-9
    sk_vec = np.where(np.abs(sk_vec) < eps, eps, sk_vec)
    inv_sk = 1.0 / sk_vec

    # Build a stable inverse matrix for 1/S_{k,i}.
    # - Diagonal-like terms (candidate bus equals POI bus): set to 0 (S_{k,i} -> inf).
    # - Missing/invalid terms: use neutral fallback 1/S_k.
    inv_ski_sub = np.zeros_like(ski_sub, dtype=float)
    target_poi_ids = [int(poi_ids[i]) for i in idx_target]
    for i in range(ski_sub.shape[0]):
        poi_bus = target_poi_ids[i]
        for k in range(ski_sub.shape[1]):
            cand_bus = cand_ids_used[k]
            ski = ski_sub[i, k]
            if cand_bus == poi_bus:
                inv_ski_sub[i, k] = 0.0
            elif np.isnan(ski) or abs(ski) < eps:
                inv_ski_sub[i, k] = inv_sk[k]
            else:
                inv_ski_sub[i, k] = 1.0 / ski

    def compute_scr_after_g(G):
        G = np.asarray(G, dtype=float)
        with np.errstate(divide='ignore', invalid='ignore', over='ignore', under='ignore'):
            numerator = 1.0 + np.dot(G, inv_sk)
            denominator = 1.0 + np.dot(inv_ski_sub, G)

            # Keep denominator in a numerically valid range for optimizer probing.
            denominator = np.where(~np.isfinite(denominator), eps, denominator)
            denominator = np.where(np.abs(denominator) < eps, eps, denominator)

            scr = scr_base_sub * (numerator / denominator)

        # Always return finite values to prevent optimizer crashes.
        scr = np.nan_to_num(scr, nan=-1e9, posinf=1e9, neginf=-1e9)
        return scr

    def objective(G):
        G = np.asarray(G, dtype=float)
        if not np.all(np.isfinite(G)):
            return 1e18
        return float(np.sum(np.maximum(G, 0.0)))

    def cons_vector(G):
        c = compute_scr_after_g(G) - target_scr
        c = np.nan_to_num(c, nan=-1e9, posinf=1e9, neginf=-1e9)
        return c

    nvar = len(cand_ids_used)
    g_upper = max(1e4, 20.0 * float(np.nanmax(sk_vec)))
    bounds = Bounds([0.0] * nvar, [g_upper] * nvar)
    nlc = NonlinearConstraint(cons_vector, lb=np.zeros(len(scr_base_sub)), ub=np.full(len(scr_base_sub), np.inf))

    best = None

    # Equivalent LP from SCR constraint:
    # SCR_i0 * (1 + a^T G) / (1 + b_i^T G) >= target
    # -> (SCR_i0 * a - target * b_i)^T G >= target - SCR_i0
    A_lp = []
    b_lp = []
    for i in range(len(scr_base_sub)):
        lhs = (scr_base_sub[i] * inv_sk) - (target_scr * inv_ski_sub[i, :])
        rhs = target_scr - scr_base_sub[i]
        A_lp.append(lhs)
        b_lp.append(rhs)

    A_lp = np.array(A_lp, dtype=float)
    b_lp = np.array(b_lp, dtype=float)

    try:
        lp_res = linprog(
            c=np.ones(nvar),
            A_ub=-A_lp,
            b_ub=-b_lp,
            bounds=[(0.0, g_upper)] * nvar,
            method='highs'
        )

        if lp_res is not None and getattr(lp_res, 'success', False):
            g_try = np.maximum(np.asarray(lp_res.x, dtype=float), 0.0)
            cons_min = float(np.min(cons_vector(g_try)))
            if cons_min >= -1e-5:
                best = {'x': g_try, 'obj': float(np.sum(g_try)), 'method': 'linprog-highs', 'cons_min': cons_min}
    except Exception:
        pass

    # Fallback to SLSQP only when LP did not produce a feasible point.
    if best is None:
        start_sets = [
            np.zeros(nvar),
            np.ones(nvar),
            np.full(nvar, 5.0),
            np.full(nvar, 20.0),
        ]
        for x0 in start_sets:
            try:
                result = minimize(
                    objective,
                    x0,
                    method='SLSQP',
                    bounds=bounds,
                    constraints=[nlc],
                    options={'disp': False, 'maxiter': 1000}
                )
            except Exception:
                continue

            if not hasattr(result, 'x'):
                continue

            g_try = np.maximum(result.x, 0.0)
            cons_min = float(np.min(cons_vector(g_try)))
            feasible = cons_min >= -1e-5
            obj_val = float(np.sum(g_try))

            if feasible:
                if best is None or obj_val < best['obj']:
                    best = {'x': g_try, 'obj': obj_val, 'method': 'SLSQP', 'cons_min': cons_min}

    if best is None:
        print("Sizing optimization failed: no feasible solution found for target SCR %.2f." % target_scr)
        return []

    g_opt = np.maximum(best['x'], 0.0)

    rows = []
    for i, c_bus in enumerate(cand_ids_used):
        rows.append([int(c_bus), float(g_opt[i])])

    scr_after_cont = compute_scr_after_g(g_opt)
    print("Sizing optimization completed using %s." % best['method'])
    print("Total capacity of GSD required to achieve desired grid strength")
    print("GSD = %.4f MVA" % float(np.sum(g_opt)))
    print("Minimum SCR after addition of GSDs: %.4f" % float(np.min(scr_after_cont)))
    return rows
