"""
Multi-year Roth-conversion as MIXED-INTEGER OPTIMAL CONTROL (dynamic programming).

The single-year problem (milp_retire.py) is a MILP because of the IRMAA integer step. The MULTI-year
problem adds STATE: a traditional-IRA balance that grows, and after age 73 throws off Required Minimum
Distributions (RMDs) that are forced taxable income (Pub 590-B). A conversion c_t this year is taxed
now but shrinks every future RMD -- so years are COUPLED through the balance. You can't optimize each
year alone.

Why a real method is required (not enumeration): choosing conversions (c_0,...,c_{T-1}) jointly on a
grid of G amounts per year over T years is G^T combinations -- astronomically infeasible. Dynamic
programming over the one-dimensional balance state is O(T . |B| . G): each stage solves the non-convex
single-year subproblem (the same torpedo + IRMAA cost surface), and Bellman stitches them. This is the
mixed-integer optimal-control payoff -- the same reason the circuit needs global methods, now in time.

Everything tax-related comes from retire_tax.py (each constant cited to a primary document):
  - tax surface (brackets, SS torpedo, LTCG stacking, NIIT, IRMAA) : i1040 / Pub 915 / Form 8960 / FR
  - RMD divisors + age-73 start                                    : Pub 590-B, Table III
Modeling assumptions that are NOT tax facts (growth rate, discount rate, horizon, the rate at which a
leftover traditional balance is eventually taxed) are explicit parameters, not buried constants.
"""
import numpy as np
from retire_tax import total_tax, rmd

def stage_tax(balance, c, age, P):
    """This year's total federal tax: ordinary = pension + RMD(balance) + Roth conversion c."""
    r = rmd(balance, age)
    ordinary = P["pension"] + r + c
    age65 = 1 if age >= 65 and P["status"] in ("single", "hoh") else (2 if age >= 65 else 0)
    t = total_tax(ordinary, P["ss"], P["ltcg"], P["status"], age65)
    return t["total"], r

def solve_dp(P, M=161, G=81):
    """Backward induction over a discretized traditional-IRA balance. Returns optimal conversion path."""
    a0, T, g, d = P["age0"], P["years"], P["growth"], P["discount"]
    rt = P["terminal_rate"]
    Bmax = P["B0"] * 2.0                                  # balance can grow before RMDs draw it down
    grid = np.linspace(0.0, Bmax, M)
    disc = [(1.0 / (1.0 + d)) ** t for t in range(T + 1)]

    # terminal value: leftover traditional balance carries a deferred tax liability at rate rt (PV'd)
    V = disc[T] * rt * grid
    policy = np.zeros((T, M))
    for t in range(T - 1, -1, -1):
        age = a0 + t
        Vn = np.empty(M)
        for i, B in enumerate(grid):
            r = rmd(B, age)
            cmax = max(B - r, 0.0)                        # can't convert below the forced RMD draw
            cs = np.linspace(0.0, cmax, G)
            best, bestc = np.inf, 0.0
            for c in cs:
                tax, _ = stage_tax(B, c, age, P)
                Bn = max((B - r - c) * (1.0 + g), 0.0)
                cont = np.interp(Bn, grid, V)            # value-to-go, interpolated on the grid
                tot = disc[t] * tax + cont
                if tot < best:
                    best, bestc = tot, c
            Vn[i] = best; policy[t, i] = bestc
        V = Vn
    # forward simulate the optimal path from the true B0
    B = P["B0"]; path = []
    totpv = 0.0
    for t in range(T):
        age = a0 + t
        c = float(np.interp(B, grid, policy[t]))
        r = rmd(B, age)
        c = min(c, max(B - r, 0.0))
        tax, _ = stage_tax(B, c, age, P)
        totpv += disc[t] * tax
        path.append(dict(age=age, balance=round(B), rmd=round(r), conversion=round(c), tax=round(tax)))
        B = max((B - r - c) * (1.0 + g), 0.0)
    totpv += disc[T] * rt * B
    return dict(pv_total=round(totpv), terminal_balance=round(B), path=path)

def baseline_no_conversion(P):
    """Take only the forced RMDs, never convert -- the do-nothing policy, for comparison."""
    a0, T, g, d = P["age0"], P["years"], P["growth"], P["discount"]
    rt = P["terminal_rate"]; disc = [(1.0/(1.0+d))**t for t in range(T+1)]
    B = P["B0"]; totpv = 0.0; path = []
    for t in range(T):
        age = a0 + t
        tax, r = stage_tax(B, 0.0, age, P)
        totpv += disc[t] * tax
        path.append(dict(age=age, balance=round(B), rmd=round(r), conversion=0, tax=round(tax)))
        B = max((B - r) * (1.0 + g), 0.0)
    totpv += disc[T] * rt * B
    return dict(pv_total=round(totpv), terminal_balance=round(B), path=path)

if __name__ == "__main__":
    u = lambda x: f"${x:,.0f}"
    P = dict(status="single", age0=65, years=25, B0=900000, pension=22000, ss=30000, ltcg=5000,
             growth=0.05, discount=0.03, terminal_rate=0.24)
    base = baseline_no_conversion(P)
    opt = solve_dp(P)
    print("Retiree: single, age 65, $900k traditional IRA, $22k pension, $30k SS, $5k LTCG/yr")
    print(f"  growth 5%/yr, discount 3%/yr, leftover taxed at 24%, 25-year horizon\n")
    print(f"  do-nothing (RMDs only)   PV lifetime tax = {u(base['pv_total'])}"
          f"   leftover IRA = {u(base['terminal_balance'])}")
    print(f"  DP-optimal conversions   PV lifetime tax = {u(opt['pv_total'])}"
          f"   leftover IRA = {u(opt['terminal_balance'])}")
    print(f"  --> PV tax saved by optimal Roth-conversion schedule: {u(base['pv_total']-opt['pv_total'])}\n")
    G, T = 81, P["years"]
    print(f"  enumeration would be G^T = {G}^{T} ~= 10^{round(T*np.log10(G))} policies (infeasible);")
    print(f"  DP is T.|B|.G = {T*161*G:,} stage evaluations.\n")
    print("  optimal conversion schedule (first 15 years):")
    print(f"    {'age':>4} {'IRA bal':>11} {'RMD':>9} {'convert':>9} {'tax':>9}")
    for row in opt["path"][:15]:
        print(f"    {row['age']:>4} {u(row['balance']):>11} {u(row['rmd']):>9} "
              f"{u(row['conversion']):>9} {u(row['tax']):>9}")
    import json
    json.dump({"optimal":opt["path"], "baseline":base["path"],
               "pv_opt":opt["pv_total"], "pv_base":base["pv_total"]},
              open("/tmp/multiyear_path.json","w"))
