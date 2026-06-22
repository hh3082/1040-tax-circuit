"""
S-corp reasonable-compensation optimizer (tax year 2025) — Python reference.

An S-corp owner splits the profit into W-2 *reasonable compensation* (subject to payroll tax) and
a *distribution* (not). Lower comp saves payroll tax, but above the QBI threshold the deduction is
capped at 50% of W-2 wages, so comp that is too low chokes the QBI deduction. The optimizer sweeps
comp to minimize total federal tax (income tax + both FICA halves), respecting a reasonable-comp
floor. The optimum sits where the 50%-of-wages limit just unlocks the full 20%-of-QBI deduction —
the reasonable-comp <-> QBI <-> payroll-tax trade-off.

Reasonable compensation is a facts-and-circumstances legal standard, not a number the IRS lets you
minimize freely; the floor here is exogenous.
"""
from schedule_c import tax, qbi_ded, STD, WAGEBASE

def scorp(profit, status, other, w):
    emp_fica = min(w, WAGEBASE) * 0.062 + w * 0.0145      # employer half (corp-deductible)
    ee_fica  = min(w, WAGEBASE) * 0.062 + w * 0.0145      # employee half
    dist = max(profit - w - emp_fica, 0.0)                # pass-through distribution
    agi = other + w + dist
    tb4 = max(agi - STD[status], 0.0)
    qd = qbi_ded(dist, tb4, status, w2=w, ubia=0.0)       # W-2 wages = comp drive the QBI wage limit
    taxable = max(tb4 - qd, 0.0); income_tax = tax(taxable, status)
    return dict(comp=w, distribution=dist, payroll_tax=emp_fica + ee_fica, qbi_deduction=qd,
                taxable=taxable, income_tax=income_tax, total_tax=income_tax + emp_fica + ee_fica)

def optimize(profit, status, other=0.0, floor=0.0, step=250):
    best, curve = None, []
    w = floor
    while w <= profit:
        r = scorp(profit, status, other, w); curve.append((w, r["total_tax"]))
        if best is None or r["total_tax"] < best["total_tax"]: best = r
        w += step
    return best, curve

if __name__ == "__main__":
    u = lambda x: f"${x:,.0f}"
    best, _ = optimize(300000, "single", floor=60000)
    hi = scorp(300000, "single", 0, 300000); lo = scorp(300000, "single", 0, 60000)
    print("$300k profit, single:")
    print("  optimal comp", u(best["comp"]), "| distribution", u(best["distribution"]),
          "| QBI", u(best["qbi_deduction"]), "| payroll", u(best["payroll_tax"]),
          "| total", u(best["total_tax"]), "  (expect ~$83,750 / $65,387)")
    print("  vs all-salary", u(hi["total_tax"]), "(QBI", u(hi["qbi_deduction"]) + ")",
          "| vs floor-comp", u(lo["total_tax"]), "(QBI", u(lo["qbi_deduction"]) + ", wage-limited)")
    print("  optimizer saves", u(min(hi["total_tax"], lo["total_tax"]) - best["total_tax"]), "vs the better naive choice")
