"""
Schedule C self-employed circuit (tax year 2025) — Python reference for the web calculator.

How it extends the 1040 circuit:
  net profit (Sch C line 31) -> Schedule 1 -> 1040 line 9 (income)
  self-employment tax        -> Schedule SE -> Schedule 2 (added to total tax)
  adjustments (1/2 SE tax, SEP/Solo-401(k), SE-health) lower AGI
  QBI deduction (Form 8995 / 8995-A) lowers taxable income

The SEP/Solo-401(k) employer contribution is the Pub. 560 retirement *fixed point*: a 25% plan
becomes 20% of (profit - 1/2 SE tax), the closed-form resolution of the circular
"contribution depends on net earnings depends on contribution".

Sole proprietor: no W-2 wages and no qualified property (UBIA = 0), so QBI is wage-limited toward
$0 above the threshold (Form 8995-A) — the structural reason high earners consider an S corp.
"""
BRACKETS = {
 "single": [(0,.10),(11925,.12),(48475,.22),(103350,.24),(197300,.32),(250525,.35),(626350,.37)],
 "mfj":    [(0,.10),(23850,.12),(96950,.22),(206700,.24),(394600,.32),(501050,.35),(751600,.37)],
 "hoh":    [(0,.10),(17000,.12),(64850,.22),(103350,.24),(197300,.32),(250525,.35),(626350,.37)]}
BRACKETS["qss"] = BRACKETS["mfj"]
BRACKETS["mfs"] = [(0,.10),(11925,.12),(48475,.22),(103350,.24),(197300,.32),(250525,.35),(375800,.37)]
STD  = {"single":15750,"mfs":15750,"mfj":31500,"qss":31500,"hoh":23625}
QTHR = {"single":197300,"mfs":197300,"mfj":394600,"qss":394600,"hoh":197300}
QRNG = {"single":50000,"mfs":50000,"mfj":100000,"qss":100000,"hoh":50000}
WAGEBASE, SEP_LIMIT = 176100, 70000

def bracket_tax(ti, st):
    b, t = BRACKETS[st], 0.0
    for i, (cut, rate) in enumerate(b):
        nxt = b[i+1][0] if i+1 < len(b) else float("inf")
        if ti > cut: t += (min(ti, nxt) - cut) * rate
    return t

def tax(ti, st):
    ti = max(ti, 0.0)
    base = ti if ti < 5 else (int(ti // 50) * 50 + 25)
    if ti >= 100000: base = ti
    return round(bracket_tax(base, st))

def se_tax(profit):
    ne = 0.9235 * profit
    return min(ne, WAGEBASE) * 0.124 + ne * 0.029

def qbi_ded(qbi, taxable_before, st, w2=0.0, ubia=0.0):
    """Form 8995 / 8995-A (non-SSTB). Below the threshold: lesser of 20% QBI and 20% taxable income.
    Above: the 20%-QBI amount is reduced toward the greater of 50% W-2 wages or 25% + 2.5% UBIA,
    phased in over the range."""
    full, cap_inc = 0.20 * max(qbi, 0.0), 0.20 * taxable_before
    thr, rng = QTHR[st], QRNG[st]
    if taxable_before <= thr:
        return min(full, cap_inc)
    wage_limited = min(full, max(0.5 * w2, 0.25 * w2 + 0.025 * ubia))
    ratio = min((taxable_before - thr) / rng, 1.0)
    return min(full - (full - wage_limited) * ratio, cap_inc)

def schedule_c(profit, status, other=0.0, premiums=0.0, sep=0.0):
    se = se_tax(profit); half = se / 2.0
    sep_max = min(0.20 * (profit - half), SEP_LIMIT)      # Pub 560 closed-form fixed point
    retire = min(sep, sep_max)
    se_health = min(premiums, profit - half - retire)     # 162(l) cap (PTC interaction: see Pub 974 / main page)
    qbi = profit - half - retire - se_health
    agi = other + profit - half - retire - se_health
    tb4 = max(agi - STD[status], 0.0)
    qd = qbi_ded(qbi, tb4, status, w2=0.0, ubia=0.0)      # sole prop: no wages / no UBIA
    taxable = max(tb4 - qd, 0.0); income_tax = tax(taxable, status)
    return dict(se_tax=se, half_se=half, sep_max=sep_max, retire=retire, se_health=se_health,
                agi=agi, taxable_before_qbi=tb4, qbi_deduction=qd, taxable=taxable,
                income_tax=income_tax, total_tax=income_tax + se, eff=(income_tax + se) / profit if profit else 0.0)

if __name__ == "__main__":
    u = lambda x: f"${x:,.0f}"
    r = schedule_c(100000, "single")
    print("$100k sole prop, single:", "SE tax", u(r["se_tax"]), "| QBI", u(r["qbi_deduction"]),
          "| total", u(r["total_tax"]), "| eff", f"{100*r['eff']:.1f}%", "  (expect $22,624 / $15,437)")
    rm = schedule_c(100000, "single", sep=r["sep_max"])
    print("  max SEP", u(r["sep_max"]), "-> total", u(rm["total_tax"]), "saves", u(r["total_tax"] - rm["total_tax"]))
    r2 = schedule_c(250000, "single")
    print("$250k sole prop:", "QBI", u(r2["qbi_deduction"]), "(wage-limited above threshold)",
          "| total", u(r2["total_tax"]))
