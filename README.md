# The 1040 Tax Circuit

An educational, interactive model of **U.S. Form 1040 (tax year 2025) as a computation circuit** — a directed graph of signed arithmetic with two feedback loops — plus a live calculator that runs the circuit in your browser and finds the lever vector that minimizes your effective federal tax rate.

🔗 **Live site:** https://hh3082.github.io/1040-tax-circuit/

## What it shows

- **The structure.** Number the lines of Form 1040 and Schedules 1–3 and you get a DAG: every line references only earlier lines, so the line numbering is a topological sort and the return fills in one pass. Each edge is a signed operation (`Σ add`, `− subtract`, `× bracket rate`, `clamp max(·,0)`).
- **The two cycles.** Two pairs of lines reference each other and can't be ordered away — *IRA deduction ↔ taxable Social Security* and *self-employed-health deduction ↔ premium tax credit*. Each is a strongly connected component solved by a fixed-point iteration; both converge because the loop gain (a product of tax rates) is `< 1`.
- **The levers.** Standard-vs-itemized, traditional IRA / HSA contributions, the Saver's Credit, and filing status are the degrees of freedom. The calculator's optimizer searches them to minimize tax.

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
