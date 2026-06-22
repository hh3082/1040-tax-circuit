"""
Single-year Roth-conversion analysis — built on retire_tax.py (all rules from primary documents).

A retiree converts `c` dollars from traditional to Roth this year; the conversion is ordinary income.
We compute the EFFECTIVE MARGINAL COST of the next conversion dollar as a function of c. Unlike the
S-corp problem (convex), this curve is NON-CONVEX: the Social Security "torpedo" makes marginal rates
hump up then fall, and each IRMAA MAGI tier crossing adds a discrete lump (a near-vertical spike).
That non-convexity is exactly why the LP/line-search reasoning breaks and a global/MILP method is
needed (essential once it becomes the multi-year problem).

Single-year objective (max net benefit vs a target future marginal rate r*):
    maximize over c>=0:  r* * c  -  [ cost(c) - cost(0) ]
where cost(c) = income tax + NIIT + IRMAA at ordinary income (ordinary + c).
For 1-D this is solved exactly by a fine grid; the point here is the shape, not the dimensionality.
"""
import json
from retire_tax import total_tax, irmaa_partb_annual, ss_taxable, std_deduction

def cost(c, R):
    return total_tax(R["ordinary"] + c, R["ss"], R["ltcg"], R["status"], R.get("age65", 1))["total"]

def marginal_curve(R, cmax, step=250):
    """Effective marginal cost of the next conversion dollar, sampled over c in [0, cmax]."""
    pts = []
    for c in range(0, int(cmax) + 1, step):
        m = (cost(c + step, R) - cost(c, R)) / step
        pts.append((c, round(100 * m, 2)))
    return pts

def irmaa_cliffs(R, cmax):
    """The conversion amounts at which MAGI crosses an IRMAA tier edge (the discrete spikes)."""
    edges = [106000, 133000, 167000, 200000, 500000] if R["status"] not in ("mfj","qss") \
            else [212000, 266000, 334000, 400000, 750000]
    out = []
    for e in edges:
        # MAGI(c) = ordinary + c + ss_taxable(...) + ltcg ; find c where MAGI hits e (ss is ~capped here)
        for c in range(0, int(cmax) + 1, 50):
            v = total_tax(R["ordinary"] + c, R["ss"], R["ltcg"], R["status"], R.get("age65", 1))
            if v["agi"] >= e:
                out.append((e, c)); break
    return out

def optimize(R, r_star, cmax, step=100):
    base = cost(0, R); best = None
    for c in range(0, int(cmax) + 1, step):
        benefit = r_star * c - (cost(c, R) - base)
        if best is None or benefit > best[0]:
            best = (benefit, c)
    return dict(opt_conversion=best[1], net_benefit=round(best[0]), avg_rate_on_conversion=
                round(100 * (cost(best[1], R) - base) / best[1], 2) if best[1] else 0.0)

if __name__ == "__main__":
    # A retiree with room to convert: modest ordinary income, sizable SS, some gains, on Medicare.
    R = dict(status="single", ordinary=22000, ss=30000, ltcg=5000, age65=1)
    cmax = 160000
    curve = marginal_curve(R, cmax)
    cliffs = irmaa_cliffs(R, cmax)
    print("sample retiree:", R)
    print("baseline tax (c=0):", f"${cost(0,R):,.0f}")
    # show the torpedo hump: marginal rate at low vs mid conversion
    lo = [m for c,m in curve if c==2000][0]; mid = [m for c,m in curve if c==12000][0]
    print(f"marginal rate at +$2k: {lo}%   at +$12k: {mid}%   (the SS-torpedo hump)")
    print("IRMAA tier crossings (conversion $ where MAGI hits a tier edge):")
    for e,c in cliffs: print(f"   MAGI ${e:,}  at conversion ${c:,}")
    for r in (0.22, 0.24):
        o = optimize(R, r, cmax)
        print(f"optimal conversion if future rate r*={int(r*100)}%: ${o['opt_conversion']:,}  "
              f"(avg cost {o['avg_rate_on_conversion']}%, net benefit ${o['net_benefit']:,})")
    json.dump({"curve":curve, "cliffs":cliffs}, open("/tmp/single_year_curve.json","w"))
    print("curve points:", len(curve))
