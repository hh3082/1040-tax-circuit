"""
Single-year Roth-conversion MILP — recovers the global optimum of the NON-CONVEX cost(c).

Why this is a MILP and not an LP (contrast with scorp.py, which is convex -> LP):
  cost(c) = income tax + LTCG tax + NIIT + IRMAA, as a function of the conversion c, is
    (a) piecewise-linear but NON-CONVEX  (the Social Security torpedo makes the marginal rate
        rise then fall -- Pub 915 Worksheet 1), and
    (b) DISCONTINUOUS                    (each IRMAA MAGI-tier edge adds a lump -- FR 2024-26474).
  A convex PWL minimizes with a plain LP; a non-convex/discontinuous one does not. We split it:
    * the continuous part  T(c) = income+LTCG+NIIT  -> exact PWL via the SOS2 (lambda) method,
      with breakpoints placed at every kink so the representation is EXACT, not approximate;
    * the discontinuous IRMAA step  -> tier-selection BINARIES z_k with big-M on MAGI(c),
      exactly as the 1040 MILP handles the Saver's-Credit step (milp.py).
  Decision variable: c >= 0 (dollars converted). Objective: maximize  r* . c - (cost(c)-cost(0)),
  i.e. bank the future avoided-tax r* per converted dollar, pay this year's true marginal cost.

All tax CONSTANTS come from retire_tax.py (each cited to a primary document). The MILP itself is a
modeling choice over that documented engine -- the same separation used throughout the circuit.
"""
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
from retire_tax import (total_tax, ordinary_tax, ltcg_tax, niit, ss_taxable,
                        std_deduction, IRMAA_B, IRMAA_BASE)

def _continuous_cost(c, R):
    """T(c) = income tax + LTCG tax + NIIT  (everything EXCEPT the IRMAA step) at conversion c."""
    o = R["ordinary"] + c
    ss_inc = ss_taxable(R["ss"], o + R["ltcg"], R["status"])
    agi = o + ss_inc + R["ltcg"]
    taxable = max(agi - std_deduction(R["status"], R.get("age65", 1)), 0.0)
    ord_taxable = max(taxable - R["ltcg"], 0.0)
    inc = ordinary_tax(ord_taxable, R["status"]) + ltcg_tax(R["ltcg"], ord_taxable, R["status"])
    return inc + niit(R["ltcg"], agi, R["status"])

def _magi(c, R):
    return total_tax(R["ordinary"] + c, R["ss"], R["ltcg"], R["status"], R.get("age65", 1))["agi"]

def _kinks(R, cmax, scan=25.0):
    """Find every c where the slope of T(c) changes -> exact PWL breakpoints (T is linear between).
    Slope is rounded to 1e-3 so the cents-rounding staircase in ss_taxable (Pub 915 worksheets round
    to the penny) collapses to its true handful of structural kinks (torpedo on/off, bracket and LTCG
    breakpoint crossings)."""
    cs = np.arange(0, cmax + scan, scan)
    T = np.array([_continuous_cost(c, R) for c in cs])
    slope = np.round(np.diff(T) / scan, 3)
    bp = [0.0]
    for i in range(1, len(slope)):
        if slope[i] != slope[i-1]:
            bp.append(float(cs[i]))          # slope changed entering breakpoint cs[i]
    bp.append(float(cmax))
    return sorted(set(bp))

def _irmaa_bands(R):
    """Reachable (lower, upper, annual-surcharge) MAGI bands for this filer, from IRMAA_B."""
    joint = R["status"] in ("mfj", "qss")
    bands, lo = [], -1e18
    for s_edge, j_edge, prem in IRMAA_B:
        up = j_edge if joint else s_edge
        bands.append((lo, up, round((prem - IRMAA_BASE) * 12, 2)))
        lo = up
    return bands

def solve(R, r_star, cmax=160000):
    # ---- exact PWL of the continuous cost over breakpoints at the kinks ----
    bp = _kinks(R, cmax)
    n = len(bp)                                   # breakpoints i = 0..n-1 ; segments j = 0..n-2
    Ti = np.array([_continuous_cost(c, R) for c in bp])
    Mi = np.array([_magi(c, R) for c in bp])
    ci = np.array(bp)
    # add cliff breakpoints so MAGI(c) hits each IRMAA edge exactly (refine PWL there)
    bands = _irmaa_bands(R)
    edges = [u for (_, u, _) in bands if np.isfinite(u) and u <= Mi[-1]]
    extra = []
    for e in edges:
        c = float(np.interp(e, Mi, ci))           # MAGI is monotone in c here -> invertible
        while c > 0 and _magi(c, R) > e:          # snap down to the last dollar in the cheaper tier
            c -= 1.0
        extra.append(max(c, 0.0))
    allc = sorted(set(list(ci) + extra))
    ci = np.array(allc); n = len(ci)
    Ti = np.array([_continuous_cost(c, R) for c in ci])
    Mi = np.array([_magi(c, R) for c in ci])
    K = len(bands)

    # ---- variable layout: [lambda_0..lambda_{n-1}] [y_0..y_{n-2}] [z_0..z_{K-1}] ----
    nL, nY, nZ = n, n - 1, K
    N = nL + nY + nZ
    iL = lambda i: i
    iY = lambda j: nL + j
    iZ = lambda k: nL + nY + k
    BIGM = float(Mi[-1] - Mi[0] + 1e6)

    rows, lbs, ubs = [], [], []
    def row(pairs, lo, hi):
        a = np.zeros(N)
        for idx, v in pairs: a[idx] += v
        rows.append(a); lbs.append(lo); ubs.append(hi)

    # convex-combination + SOS2 adjacency
    row([(iL(i), 1.0) for i in range(n)], 1.0, 1.0)                 # sum lambda = 1
    row([(iY(j), 1.0) for j in range(n-1)], 1.0, 1.0)              # sum y = 1 (one active segment)
    row([(iL(0), 1.0), (iY(0), -1.0)], -np.inf, 0.0)               # lambda_0 <= y_0
    for i in range(1, n-1):
        row([(iL(i), 1.0), (iY(i-1), -1.0), (iY(i), -1.0)], -np.inf, 0.0)   # lambda_i <= y_{i-1}+y_i
    row([(iL(n-1), 1.0), (iY(n-2), -1.0)], -np.inf, 0.0)           # lambda_{n-1} <= y_{n-2}
    # one IRMAA tier active, linked to MAGI = sum lambda_i Mi
    row([(iZ(k), 1.0) for k in range(K)], 1.0, 1.0)
    for k, (lo, up, _) in enumerate(bands):
        if np.isfinite(lo):                                        # MAGI >= lo - M(1-z_k)
            row([(iL(i), Mi[i]) for i in range(n)] + [(iZ(k), -BIGM)], lo - BIGM, np.inf)
        if np.isfinite(up):                                        # MAGI <= up + M(1-z_k)
            row([(iL(i), Mi[i]) for i in range(n)] + [(iZ(k),  BIGM)], -np.inf, up + BIGM)

    A = np.array(rows)
    con = LinearConstraint(A, np.array(lbs), np.array(ubs))
    integ = np.zeros(N); integ[nL:] = 1                            # y, z are binary
    lb = np.zeros(N); ub = np.ones(N)
    bnds = Bounds(lb, ub)

    # minimize  T_var + IRMAA_var - r* . c   (= -net benefit, up to the constant -base+r*0)
    obj = np.zeros(N)
    for i in range(n): obj[iL(i)] = Ti[i] - r_star * ci[i]
    for k, (_, _, surch) in enumerate(bands): obj[iZ(k)] = surch

    res = milp(c=obj, constraints=con, integrality=integ, bounds=bnds)
    lam = res.x[:nL]
    c_opt = float(np.floor(lam @ ci))             # whole-dollar conversion; floor never crosses a tier up
    base = total_tax(R["ordinary"], R["ss"], R["ltcg"], R["status"], R.get("age65", 1))["total"]
    cost_opt = total_tax(R["ordinary"] + c_opt, R["ss"], R["ltcg"], R["status"], R.get("age65", 1))["total"]
    net = r_star * c_opt - (cost_opt - base)
    return dict(opt_conversion=round(c_opt), net_benefit=round(net), n_breakpoints=n,
                avg_rate=round(100*(cost_opt-base)/c_opt, 2) if c_opt > 1 else 0.0,
                status=res.status, success=res.success)

if __name__ == "__main__":
    import single_year as g
    R = dict(status="single", ordinary=22000, ss=30000, ltcg=5000, age65=1)
    print("MILP vs grid  (retiree:", R, ")\n")
    print(f"{'r*':>5} | {'MILP c*':>10} {'net':>8} | {'grid c*':>10} {'net':>8} | match")
    for r in (0.20, 0.22, 0.24, 0.26, 0.30):
        m = solve(R, r); gg = g.optimize(R, r, 160000, step=100)
        ok = abs(m["opt_conversion"] - gg["opt_conversion"]) <= 100
        print(f"{int(r*100):>4}% | {m['opt_conversion']:>10,} {m['net_benefit']:>8,} | "
              f"{gg['opt_conversion']:>10,} {gg['net_benefit']:>8,} | {'OK' if ok else 'XX'}"
              f"   (n_bp={m['n_breakpoints']}, milp status={m['status']})")
