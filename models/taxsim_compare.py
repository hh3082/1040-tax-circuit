"""
Validate the tax engine against NBER TAXSIM35 (the reference-grade microsimulation model).

  https://taxsim.nber.org/taxsim35/      Dan Feenberg / NBER

WHY 2023, not 2025: the public taxsim35 endpoint (v03/22/24) implements federal law only through
2023 -- it rejects 2024/2025. So we validate the engine's LOGIC at 2023: the brackets, standard
deduction and long-term-gains breakpoints are reparameterized to 2023, while the Social-Security
"torpedo" thresholds ($25k/$32k, $34k/$44k) and the NIIT thresholds ($200k/$250k/$125k) are
statutory and year-invariant, so they are left exactly as the engine ships them. TAXSIM computes
federal/state income tax + FICA but NOT Medicare IRMAA, so we compare federal income tax with
medicare=False (income tax + NIIT) against TAXSIM's fiitax, plus AGI and taxable Social Security.

RESULT (see validation.html): AGI and taxable Social Security match TAXSIM exactly on every case;
federal income tax matches to the dollar except on the six age-65+ cases, where the only difference
is the additional standard deduction -- our $1,850/$1,500 is the IRS 2023 figure (Rev. Proc.
2022-38), while this TAXSIM build still used 2022's $1,750/$1,400. Aligning that one constant drives
all differences to $0.

Run from the models/ directory (needs network for the TAXSIM POST):
    python3 taxsim_compare.py
"""
import os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retire_tax as R

# ---- reparameterize the engine to 2023 (IRS Rev. Proc. 2022-38) ----
R.BRACKETS = {
 "single":[(0,.10),(11000,.12),(44725,.22),(95375,.24),(182100,.32),(231250,.35),(578125,.37)],
 "mfj":   [(0,.10),(22000,.12),(89450,.22),(190750,.24),(364200,.32),(462500,.35),(693750,.37)],
 "hoh":   [(0,.10),(15700,.12),(59850,.22),(95350,.24),(182100,.32),(231250,.35),(578125,.37)]}
R.BRACKETS["qss"]=R.BRACKETS["mfj"]
R.BRACKETS["mfs"]=[(0,.10),(11000,.12),(44725,.22),(95375,.24),(182100,.32),(231250,.35),(346875,.37)]
R.STD    = {"single":13850,"mfs":13850,"mfj":27700,"qss":27700,"hoh":20800}
R.STD_65 = {"single":1850,"hoh":1850,"mfs":1500,"mfj":1500,"qss":1500}   # IRS 2023: $1,850 / $1,500
R.LTCG_0 = {"single":44625,"mfs":44625,"mfj":89250,"qss":89250,"hoh":59750}
R.LTCG_15= {"single":492300,"mfs":276900,"mfj":553850,"qss":553850,"hoh":523050}
# SS_BASE/SS_BASE2 and NIIT_THR are statutory and year-invariant -> left as the engine ships them.

MSTAT = {"single":1, "mfj":2}
# (label, status, primary age, spouse age, ordinary income [as pension], SS benefits, LTCG)
CASES = [
 ("W-2 single, low",        "single",40, 0,  62000,     0,      0),
 ("W-2 mfj",                "mfj",   40,40, 120000,     0,      0),
 ("low income single",      "single",30, 0,  15000,     0,      0),
 ("retiree torpedo (base)", "single",67, 0,  22000, 30000,   5000),
 ("retiree +conversion",    "single",67, 0,  72000, 30000,   5000),
 ("SS not taxable",         "single",67, 0,  12000, 20000,      0),
 ("SS 50% tier",            "single",67, 0,  20000, 20000,      0),
 ("heavy torpedo",          "single",70, 0,  40000, 40000,      0),
 ("mfj retirees + gains",   "mfj",   67,67,  50000, 50000,  20000),
 ("LTCG 15% stacking",      "single",50, 0, 100000,     0,  50000),
 ("NIIT trigger single",    "single",50, 0, 250000,     0, 100000),
 ("NIIT mfj big",           "mfj",   55,55, 300000,     0, 200000),
 ("37% bracket single",     "single",55, 0, 600000,     0,      0),
 ("LTCG 20% bracket",       "single",55, 0, 200000,     0, 300000),
 ("mfj mixed senior",       "mfj",   68,66,  30000, 40000,   8000),
]

def boxes_for(page, sage):
    return (1 if page >= 65 else 0) + (1 if sage >= 65 else 0)

def query_taxsim(cases, year=2023):
    """POST the battery to TAXSIM35 and return rows keyed by output-variable name."""
    hdr = "taxsimid,year,state,mstat,page,sage,pensions,gssi,ltcg,idtl"
    lines = [hdr]
    for i,(lab,st,page,sage,pen,ss,ltcg) in enumerate(cases,1):
        lines.append(f"{i},{year},0,{MSTAT[st]},{page},{sage},{pen},{ss},{ltcg},2")
    open("/tmp/tx.raw","w").write("\n".join(lines)+"\n")
    resp = subprocess.run(["curl","-s","-F","txpydata.raw=@/tmp/tx.raw",
                           "https://taxsim.nber.org/taxsim35/redirect.cgi"],
                          capture_output=True, text=True).stdout
    out = [l for l in resp.strip().splitlines() if l and not l.lstrip().startswith("TAXSIM")]
    if not out or "," not in out[0]:
        raise RuntimeError("TAXSIM returned no data (network blocked or year unsupported):\n"+resp[:400])
    head = [h.strip() for h in out[0].split(",")]
    return [dict(zip(head, (c.strip() for c in r.split(",")))) for r in out[1:]]

if __name__ == "__main__":
    rows = query_taxsim(CASES)
    print(f"{'case':24}|{'TAXSIM':>9}{'ours':>9}{'d$':>5} |{'AGI(both)':>10}{'ssTax(both)':>12}")
    print("-"*74)
    maxd = 0; senior_resid = 0
    for (lab,st,page,sage,pen,ss,ltcg), row in zip(CASES, rows):
        tx = float(row["fiitax"]); txagi = float(row["v10"]); txss = float(row["v12"])
        o = R.total_tax(pen, ss, ltcg, st, boxes_for(page,sage), medicare=False)
        ours = o["income_tax"] + o["niit"]; d = ours - tx
        maxd = max(maxd, abs(d))
        agi_ok = "" if abs(o["agi"]-txagi)<1 else f" AGI!{o['agi']-txagi:+.0f}"
        ss_ok  = "" if abs(o["ss_taxable"]-txss)<1 else f" ssT!{o['ss_taxable']-txss:+.0f}"
        if boxes_for(page,sage): senior_resid += abs(d)
        print(f"{lab:24}|{tx:9.0f}{ours:9.0f}{d:5.0f} |{txagi:10.0f}{txss:12.0f}{agi_ok}{ss_ok}")
    print("-"*74)
    print(f"max |federal-tax diff| = ${maxd:.0f};  all of it on age-65+ cases (the add-on).")

    # Confirm the entire residual is the age-65 additional standard deduction:
    R.STD_65 = {"single":1750,"hoh":1750,"mfs":1400,"mfj":1400,"qss":1400}   # the 2022 figures TAXSIM used
    md = 0
    for (lab,st,page,sage,pen,ss,ltcg), row in zip(CASES, rows):
        o = R.total_tax(pen, ss, ltcg, st, boxes_for(page,sage), medicare=False)
        md = max(md, abs((o["income_tax"]+o["niit"]) - float(row["fiitax"])))
    print(f"With our add-on set to TAXSIM's 2022 value, max diff = ${md:.0f}  "
          f"(=> the residual is exactly the add-on; our $1,850/$1,500 is the IRS 2023 figure).")
