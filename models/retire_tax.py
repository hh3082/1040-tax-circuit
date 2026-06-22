"""
Retirement-year tax engine (2025) — the non-convex setting, built strictly from primary documents.

Every constant below is transcribed from a retrieved source, NOT from prior knowledge:
  - ordinary brackets / std deduction / age-65 addition : 2025 Instructions for Form 1040
      (Tax Computation Worksheet; "$1,600 ($2,000 if single or head of household)" age/blind add-on)
  - taxable Social Security (the "torpedo")              : Pub. 915, Worksheet 1
      base amounts $25,000 (single/HoH/QSS), $32,000 (MFJ); 2nd tier $34,000 / $44,000;
      "Multiply line ... by 50% (0.50)" and "by 85% (0.85)" (Pub 915 lines 308, 591, 613, 626-630)
  - capital-gains stacking (0/15/20%)                    : i1040 Qualified Dividends and Capital Gain
      Tax Worksheet: line 6 breakpoints $48,350 (S/MFS), $96,700 (MFJ/QSS), $64,750 (HoH);
      line 9 taxed at 0%; line 18 "Multiply ... by 15% (0.15)"; line 13 upper breakpoints
      $533,400 (S), $300,000 (MFS), $600,050 (MFJ/QSS), $566,700 (HoH); remainder at 20%
  - NIIT                                                 : Instructions for Form 8960:
      "The NIIT is 3.8% of the lesser of" net investment income or (MAGI - threshold);
      thresholds $250,000 (MFJ), $200,000 (single/HoH), $125,000 (MFS)
  - IRMAA (Medicare Part B)                              : Federal Register 2024-26474 (govinfo),
      2025 Part B IRMAA table (MAGI tiers and total monthly premium), transcribed below.
"""

# ---- ordinary income tax (2025 Instructions for Form 1040) ----
BRACKETS = {
 "single": [(0,.10),(11925,.12),(48475,.22),(103350,.24),(197300,.32),(250525,.35),(626350,.37)],
 "mfj":    [(0,.10),(23850,.12),(96950,.22),(206700,.24),(394600,.32),(501050,.35),(751600,.37)],
 "hoh":    [(0,.10),(17000,.12),(64850,.22),(103350,.24),(197300,.32),(250525,.35),(626350,.37)]}
BRACKETS["qss"] = BRACKETS["mfj"]
BRACKETS["mfs"] = [(0,.10),(11925,.12),(48475,.22),(103350,.24),(197300,.32),(250525,.35),(375800,.37)]
STD = {"single":15750,"mfs":15750,"mfj":31500,"qss":31500,"hoh":23625}
STD_65 = {"single":2000,"hoh":2000,"mfs":1600,"mfj":1600,"qss":1600}   # i1040: $2,000 single/HoH else $1,600 per box

def std_deduction(status, age65_boxes=0):
    return STD[status] + age65_boxes * STD_65[status]

def ordinary_tax(ti, status):
    """Tax Computation Worksheet schedule (continuous; the Tax Table is its $50-row rounding)."""
    ti = max(ti, 0.0); b = BRACKETS[status]; t = 0.0
    for i, (cut, rate) in enumerate(b):
        nxt = b[i+1][0] if i+1 < len(b) else float("inf")
        if ti > cut: t += (min(ti, nxt) - cut) * rate
    return t

# ---- taxable Social Security: Pub. 915 Worksheet 1 ----
SS_BASE  = {"single":25000,"hoh":25000,"qss":25000,"mfs":25000,"mfj":32000}    # Pub 915 lines 278-283
SS_BASE2 = {"single":34000,"hoh":34000,"qss":34000,"mfs":34000,"mfj":44000}    # Pub 915 line 537 / 609
def ss_taxable(ss, other, status):
    """Worksheet 1: up to 50% then up to 85% of benefits become taxable as provisional income rises."""
    if ss <= 0: return 0.0
    b1, b2 = SS_BASE[status], SS_BASE2[status]
    prov = other + 0.5 * ss                                    # one-half of benefits + other income
    if prov <= b1: return 0.0
    if prov <= b2: return round(min(0.5 * ss, 0.5 * (prov - b1)), 2)        # 50% tier
    lower = min(0.5 * ss, 0.5 * (b2 - b1))
    return round(min(0.85 * ss, 0.85 * (prov - b2) + lower), 2)             # 85% tier (lines 613, 628-630)

# ---- capital-gains stacking: i1040 Qualified Dividends and Capital Gain Tax Worksheet ----
LTCG_0 = {"single":48350,"mfs":48350,"mfj":96700,"qss":96700,"hoh":64750}   # worksheet line 6
LTCG_15= {"single":533400,"mfs":300000,"mfj":600050,"qss":600050,"hoh":566700}  # worksheet line 13
def ltcg_tax(ltcg, ordinary_taxable, status):
    """LTCG/qualified dividends stack on top of ordinary taxable income; 0% up to line-6 breakpoint,
    15% up to line-13 breakpoint, 20% above (worksheet lines 6-9, 13, 18)."""
    if ltcg <= 0: return 0.0
    top0, top15 = LTCG_0[status], LTCG_15[status]
    start = ordinary_taxable                                   # gains sit above ordinary income
    at0  = max(0.0, min(start + ltcg, top0) - start)           # portion in the 0% band
    at15 = max(0.0, min(start + ltcg, top15) - max(start, top0))
    at20 = max(0.0, (start + ltcg) - max(start, top15))
    return round(0.0 * at0 + 0.15 * at15 + 0.20 * at20, 2)

# ---- NIIT: Instructions for Form 8960 ----
NIIT_THR = {"single":200000,"hoh":200000,"mfj":250000,"qss":250000,"mfs":125000}
def niit(nii, magi, status):
    """3.8% of the lesser of net investment income or (MAGI - threshold)."""
    return round(0.038 * max(0.0, min(nii, magi - NIIT_THR[status])), 2)

# ---- IRMAA Medicare Part B: Federal Register 2024-26474, 2025 table ----
# (single MAGI upper edge, MFJ MAGI upper edge, total monthly Part B premium); base premium $185.00
IRMAA_B = [(106000, 212000, 185.00), (133000, 266000, 259.00), (167000, 334000, 370.00),
           (200000, 400000, 480.90), (500000, 750000, 591.90), (float("inf"), float("inf"), 628.90)]
IRMAA_BASE = 185.00
def irmaa_partb_annual(magi, status):
    """Annual Part B IRMAA surcharge per person = (tier premium - base) x 12 (a pure step function of MAGI)."""
    joint = status in ("mfj", "qss")
    for s_edge, j_edge, prem in IRMAA_B:
        edge = j_edge if joint else s_edge
        if magi <= edge: return round((prem - IRMAA_BASE) * 12, 2)
    return round((IRMAA_B[-1][2] - IRMAA_BASE) * 12, 2)

# ---- RMD: Pub. 590-B Appendix B, Table III (Uniform Lifetime), 2025 ----
# age -> applicable denominator (transcribed verbatim from Pub 590-B p.67).
UNIFORM_LIFETIME = {
 72:27.4, 73:26.5, 74:25.5, 75:24.6, 76:23.7, 77:22.9, 78:22.0, 79:21.1, 80:20.2, 81:19.4,
 82:18.5, 83:17.7, 84:16.8, 85:16.0, 86:15.2, 87:14.4, 88:13.7, 89:12.9, 90:12.2, 91:11.5,
 92:10.8, 93:10.1, 94:9.5, 95:8.9, 96:8.4, 97:7.8, 98:7.3, 99:6.8, 100:6.4, 101:6.0,
 102:5.6, 103:5.2, 104:4.9, 105:4.6, 106:4.3, 107:4.1, 108:3.9, 109:3.7, 110:3.5, 111:3.4,
 112:3.3, 113:3.1, 114:3.0, 115:2.9, 116:2.8, 117:2.7, 118:2.5, 119:2.3, 120:2.0}
RMD_START_AGE = 73   # Pub 590-B: "Age 73 for tax years 2023 and later."

def rmd(balance_prior_yearend, age):
    """Required minimum distribution = prior 12/31 balance / applicable denominator (Pub 590-B,
    'Figuring the Owner's Required Minimum Distribution'). Zero before the required beginning age."""
    if age < RMD_START_AGE or balance_prior_yearend <= 0:
        return 0.0
    return balance_prior_yearend / UNIFORM_LIFETIME.get(min(int(age), 120), 2.0)

# ---- the whole return for a retiree ----
def total_tax(ordinary, ss, ltcg, status, age65_boxes=1, medicare=True):
    """ordinary = non-SS ordinary income (pension, IRA/RMD, interest, conversions);
       ss = Social Security benefits; ltcg = long-term gains + qualified dividends."""
    ss_inc = ss_taxable(ss, ordinary + ltcg, status)
    agi = ordinary + ss_inc + ltcg
    taxable = max(agi - std_deduction(status, age65_boxes), 0.0)
    ord_taxable = max(taxable - ltcg, 0.0)                     # gains sit on top
    inc_tax = ordinary_tax(ord_taxable, status) + ltcg_tax(ltcg, ord_taxable, status)
    nii_tax = niit(ltcg, agi, status)                          # NII here = the LTCG/dividends
    irmaa = irmaa_partb_annual(agi, status) if medicare else 0.0
    return dict(agi=agi, ss_taxable=ss_inc, taxable=taxable, income_tax=round(inc_tax),
                niit=nii_tax, irmaa=irmaa, total=round(inc_tax) + nii_tax + irmaa)

if __name__ == "__main__":
    u = lambda x: f"${x:,.2f}"
    # component checks against the transcribed figures
    print("ss_taxable: single, $30k other + $40k SS ->", ss_taxable(40000, 30000, "single"),
          "(prov 50k > 34k -> 85% tier)")
    print("ltcg_tax: $10k gains on $20k ordinary, single ->", ltcg_tax(10000, 20000, "single"),
          "(20k-30k all below $48,350 -> 0%)")
    print("ltcg_tax: $20k gains stacked on $40k ordinary, single ->", ltcg_tax(20000, 40000, "single"),
          "(40k-48,350 at 0%, 48,350-60k at 15% = 11,650x.15 = 1,747.50)")
    print("ltcg_tax: $20k gains on $45k ordinary, single ->", ltcg_tax(20000, 45000, "single"),
          "(part 0%, part 15% across $48,350)")
    print("niit: $50k gains, MAGI $230k single ->", niit(50000, 230000, "single"), "(3.8% x min(50k, 30k)=1140)")
    print("irmaa Part B annual: MAGI $140k single ->", irmaa_partb_annual(140000, "single"),
          "( (370-185)x12 = 2220 )")
    print("irmaa Part B annual: MAGI $205k single ->", irmaa_partb_annual(205000, "single"),
          "( (591.90-185)x12 = 4882.80 )")
    r = total_tax(60000, 40000, 15000, "single")
    print("\nretiree: $60k ordinary, $40k SS, $15k LTCG, single 65+:", {k: u(v) if isinstance(v,(int,float)) else v for k,v in r.items()})
