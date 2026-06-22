# The 1040 Tax Circuit

An educational, interactive model of **U.S. Form 1040 (tax year 2025) as a computation circuit** — a directed graph of signed arithmetic with two feedback loops — plus a live calculator that runs the circuit in your browser and finds the lever vector that minimizes your effective federal tax rate.

🔗 **Live site:** https://hh3082.github.io/1040-tax-circuit/

## What it shows

- **The structure.** Number the lines of Form 1040 and Schedules 1–3 and you get a DAG: every line references only earlier lines, so the line numbering is a topological sort and the return fills in one pass. Each edge is a signed operation (`Σ add`, `− subtract`, `× bracket rate`, `clamp max(·,0)`).
- **The two cycles.** Two pairs of lines reference each other and can't be ordered away — *IRA deduction ↔ taxable Social Security* and *self-employed-health deduction ↔ premium tax credit*. Each is a strongly connected component solved by a fixed-point iteration; both converge because the loop gain (a product of tax rates) is `< 1`.
- **The levers.** Standard-vs-itemized, traditional IRA / HSA contributions, the Saver's Credit, and filing status are the degrees of freedom. The calculator's optimizer searches them to minimize tax.
- **Small business** (`business.html`). The Schedule C self-employed circuit and the S-corp reasonable-compensation optimizer (a *convex* LP: the payroll-tax-vs-QBI trade-off).
- **Retirement** (`retirement.html`). Where the circuit goes **non-convex**: the Social Security torpedo (Pub. 915) makes the marginal cost of a Roth conversion hump up then fall, and IRMAA Medicare cliffs (Federal Register 2024-26474) add discontinuous jumps. The single-year optimum needs a **MILP** (SOS2 piecewise-linear cost + IRMAA-tier binaries with big-M); the multi-year schedule, coupled by RMDs (Pub. 590-B Uniform Lifetime Table) and balance dynamics, needs a **dynamic program** (`G^T` enumeration is infeasible). Models in `models/retire_tax.py`, `models/milp_retire.py`, `models/multiyear.py` — every constant transcribed from a primary IRS/FR source.

## Validation

The income-tax engine is checked case-by-case against **NBER's [TAXSIM35](https://taxsim.nber.org/taxsim35/)**, the reference microsimulation model. Across a 15-case battery (the SS torpedo at both inclusion tiers, capital-gains 0/15/20% stacking, NIIT, top bracket, single & joint), **AGI and taxable Social Security match exactly**, and **federal income tax matches to the dollar** except for a ≤$24 difference on age-65+ cases — which is a staleness in TAXSIM's build (it used 2022's additional standard deduction), not ours: our $1,850/$1,500 is the IRS 2023 figure (Rev. Proc. 2022-38). See [validation.html](validation.html) and reproduce with `cd models && python3 taxsim_compare.py`. (TAXSIM models income tax, not IRMAA; the reachable endpoint caps at tax year 2023, so the comparison is run at 2023 with the statutory SS/NIIT thresholds left untouched.)

## Run locally

It's a single static file — just open `index.html`, or serve the folder:

```bash
python3 -m http.server 8000   # then visit http://localhost:8000
```

All computation runs client-side; no data leaves the browser.

## ⚠️ Disclaimer

This is an **educational model with simplified assumptions** (standard deduction, full IRA deductibility, no preferential capital-gains rates; the two fixed-point loops are documented but not run in the basic calculator). Figures are illustrative and may differ from an actual return. **This is not tax, legal, or financial advice** — consult a qualified professional before acting.

## Sources

2025 Form 1040 & Schedules 1–3; the in-instruction worksheets (Tax Computation, Social Security Benefits, Standard Deduction); the 2025 standard deduction and rate schedule; Saver's Credit tiers (Form 8880); IRA phase-out (Pub. 590-A); premium tax credit applicable percentages (Rev. Proc. 2024-35 / Form 8962); SE-health ↔ PTC iteration (Pub. 974).
