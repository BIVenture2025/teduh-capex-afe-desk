# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "aaaaaaaa-0000-4000-8000-000000000002",
# META       "default_lakehouse_name": "LH_TeduhCapex",
# META       "default_lakehouse_workspace_id": "aaaaaaaa-0000-4000-8000-000000000001",
# META       "known_lakehouses": [
# META         {
# META           "id": "aaaaaaaa-0000-4000-8000-000000000002"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# NB_TeduhCapex_ERP (P38)
#
# The ERP side of the sample: the same seeded generator writes POs, GL actuals, capex budget and cost elements to Bronze. Exits with a verdict JSON.

# CELL ********************

__file__ = "/tmp/gen_teduh_capex.py"
"""gen_teduh_capex.py - P38 sample data for Teduh Samudera Energy's capex AFE desk (fictional, synthetic).

Deterministic (seed 38). Writes CSVs to ./out and control_totals.json. Data cut: actuals to 31 Oct 2026.
Seeded AFEs only: the live AFEs of the end-to-end tests are created later through the app and the flow.
"""
import json, math, os, random
from datetime import date, timedelta
import pandas as pd

SEED = 38
CUT = date(2026, 10, 31)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
rng = random.Random(SEED)

ASSETS = [("TU", "Teduh Utara", "Offshore field"), ("TS", "Teduh Selatan", "Offshore field"),
          ("TT", "Teduh Timur", "Offshore field"), ("OGT", "Onshore Gas Terminal", "Onshore terminal"),
          ("CORP", "Corporate", "Corporate")]
REQ = {"TU": "Aiman Hakim", "TS": "Siti Aisyah Kamal", "TT": "Daniel Lim", "OGT": "Kavitha Raman", "CORP": "Farid Osman"}
ASSET_MGR = {"TU": "Zulkifli Rahman", "TS": "Grace Wong", "TT": "Hafiz Jamal", "OGT": "Priya Nair", "CORP": "Nadia Rahim"}
ELEMENTS = [("ENG", "Engineering", True), ("MAT", "Materials and equipment", True), ("FAB", "Fabrication and construction", True),
            ("DRL", "Drilling services", True), ("MAR", "Marine and logistics", True), ("OWN", "Owner's costs", False),
            ("CON", "Contingency", False)]
# type: (assets allowed, amount range RM m, element weights, duration months range)
TYPES = {
    "Drilling":       (["TU", "TS", "TT"], (25, 80), {"ENG": 4, "MAT": 18, "DRL": 52, "MAR": 12, "OWN": 4, "CON": 10}, (6, 14)),
    "Facilities":     (["TU", "TS", "TT", "OGT"], (3, 30), {"ENG": 12, "MAT": 30, "FAB": 32, "MAR": 8, "OWN": 8, "CON": 10}, (10, 26)),
    "Pipeline":       (["TU", "TS", "TT", "OGT"], (8, 45), {"ENG": 10, "MAT": 34, "FAB": 30, "MAR": 10, "OWN": 6, "CON": 10}, (12, 30)),
    "IT and buildings": (["OGT", "CORP"], (0.4, 4), {"ENG": 20, "MAT": 45, "FAB": 15, "OWN": 10, "CON": 10}, (6, 15)),
    "Study":          (["TU", "TS", "TT", "OGT", "CORP"], (0.5, 3), {"ENG": 80, "OWN": 10, "CON": 10}, (4, 10)),
}
LOA = [("T1", "Asset manager", 0, 5_000_000), ("T2", "GM Projects", 5_000_000, 25_000_000), ("T3", "CEO", 25_000_000, None)]
FIN_CTRL, GM_PROJ, CEO = "Tan Mei Ling", "Rizal Ahmad", "Haris Iskandar"
TITLES = {
    "Drilling": ["infill well {n}", "sidetrack well {n}", "development well {n}"],
    "Facilities": ["gas compression upgrade", "produced water treatment revamp", "flare gas recovery unit", "power generation retrofit", "living quarters extension"],
    "Pipeline": ["infield pipeline replacement", "export pipeline intelligent pigging and repair", "subsea tie-back line"],
    "IT and buildings": ["control room network refresh", "admin building refurbishment", "ERP project costing module"],
    "Study": ["late-life abandonment study", "debottlenecking study", "carbon capture screening study"],
}


def tier_for(amount):
    for code, _, lo, hi in LOA:
        if amount > lo and (hi is None or amount <= hi):
            return code
    return "T1"


def month_ends(start, end):
    d = date(start.year, start.month, 1)
    while d <= end:
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        yield nxt - timedelta(days=1)
        d = nxt


def scurve(t):  # t in [0,1] -> cumulative share
    t = min(max(t, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def add_months(d, m):
    y, mo = divmod(d.month - 1 + m, 12)
    return date(d.year + y, mo + 1, min(d.day, 28))


def build():
    afes, lines, decisions, phasing, pos, gl = [], [], [], [], [], []
    seq = {2024: 0, 2025: 0, 2026: 0}
    plan = ([2024] * 20) + ([2025] * 22) + ([2026] * 18)
    for i, yr in enumerate(plan):
        typ = rng.choices(list(TYPES), weights=[14, 26, 16, 22, 22])[0]
        allowed, (lo, hi), weights, (dlo, dhi) = TYPES[typ]
        asset = rng.choice(allowed)
        seq[yr] += 1
        afe_no = f"TSE-AFE-{yr % 100:02d}-{seq[yr]:03d}"
        amount = round(rng.uniform(lo, hi) * 1_000_000, -4)
        raised = date(yr, rng.randint(1, 11 if yr < 2026 else 9), rng.randint(1, 28))
        title = rng.choice(TITLES[typ]).format(n=rng.randint(4, 19))
        title = f"{dict((a[0], a[1]) for a in ASSETS)[asset]} {title}"
        tier = tier_for(amount)
        fin_days = rng.randint(1, 6)
        loa_days = {"T1": rng.randint(1, 4), "T2": rng.randint(2, 8), "T3": rng.randint(5, 16)}[tier]
        submitted = raised + timedelta(days=rng.randint(0, 3))
        fin_at = submitted + timedelta(days=fin_days)
        # outcome
        r = rng.random()
        outcome = "Approved" if r > 0.08 else "Rejected"
        returned = rng.random() < 0.12
        if returned:  # finance returned once, resubmitted after a few days
            decisions.append(dict(afe_no=afe_no, step="Finance check", approver=FIN_CTRL, role="Finance controller",
                                  submitted_on=submitted, decided_on=fin_at, outcome="Returned",
                                  comment="Phasing does not match the asset WP&B; please re-phase."))
            submitted = fin_at + timedelta(days=rng.randint(2, 6))
            fin_at = submitted + timedelta(days=rng.randint(1, 3))
        decisions.append(dict(afe_no=afe_no, step="Finance check", approver=FIN_CTRL, role="Finance controller",
                              submitted_on=submitted, decided_on=fin_at, outcome="Passed", comment="Within asset capex budget."))
        approver = {"T1": ASSET_MGR[asset], "T2": GM_PROJ, "T3": CEO}[tier]
        role = {"T1": "Asset manager", "T2": "GM Projects", "T3": "CEO"}[tier]
        dec_at = fin_at + timedelta(days=loa_days)
        decisions.append(dict(afe_no=afe_no, step="LOA approval", approver=approver, role=role, submitted_on=fin_at,
                              decided_on=dec_at, outcome=outcome,
                              comment="Approved." if outcome == "Approved" else "Not in this year's priorities; resubmit with WP&B 2027."))
        dur = rng.randint(dlo, dhi)
        start = add_months(dec_at, 1)
        end = add_months(start, dur)
        status = "Rejected" if outcome == "Rejected" else ("Closed" if end <= date(2026, 6, 30) else "Approved")
        factor = rng.uniform(1.22, 1.40) if (status == "Approved" and rng.random() < 0.33) else rng.gauss(0.98, 0.05)
        afes.append(dict(afe_no=afe_no, parent_afe_no="", kind="Original", title=title, asset_code=asset, afe_type=typ,
                         requester=REQ[asset], raised_on=raised, submitted_on=submitted, decided_on=dec_at,
                         amount_rm=amount, loa_tier=tier, status=status, planned_start=start, planned_end=end,
                         _factor=factor))
        # lines
        wsum = sum(weights.values())
        alloc = {k: round(amount * w / wsum, -3) for k, w in weights.items()}
        alloc["CON"] += amount - sum(alloc.values())
        for k, v in alloc.items():
            lines.append(dict(afe_no=afe_no, element_code=k, estimate_rm=v))
        # phasing by year (planned, from the S-curve)
        for y in range(start.year, end.year + 1):
            t0 = max(0, ((date(y, 1, 1) - start).days) / max(1, (end - start).days))
            t1 = min(1, ((date(y, 12, 31) - start).days) / max(1, (end - start).days))
            share = scurve(t1) - scurve(t0)
            if share > 0.0005:
                phasing.append(dict(afe_no=afe_no, year=y, planned_rm=round(amount * share, -3)))
        if status == "Rejected":
            continue
        # spend: POs on awarded elements, direct GL on owner's costs; contingency unspent
        po_n = 0
        for k, est in alloc.items():
            el = dict((e[0], e) for e in ELEMENTS)[k]
            if k == "CON":
                continue
            fac = factor * rng.uniform(0.96, 1.04)
            if el[2]:
                n = rng.randint(1, 5)
                shares = [rng.random() + 0.3 for _ in range(n)]
                for s in shares:
                    po_n += 1
                    award_t = rng.uniform(0.0, 0.45)
                    award = start + timedelta(days=int(award_t * (end - start).days))
                    if award > CUT:
                        continue
                    val = round(est * fac * s / sum(shares), -2)
                    po_no = f"PO-{afe_no[-6:].replace('-', '')}-{po_n:02d}"
                    pos.append(dict(po_no=po_no, afe_no=afe_no, element_code=k, vendor=rng.choice(VENDORS), awarded_on=award, po_value_rm=val))
                    prev = 0.0
                    for me in month_ends(award, min(end, CUT)):
                        t = (me - award).days / max(1, (end - award).days)
                        cum = round(val * scurve(t + 0.08), 2) if me < end else val
                        amt = round(cum - prev, 2)
                        if amt > 0.5:
                            gl.append(dict(afe_no=afe_no, element_code=k, po_no=po_no, period_end=me, amount_rm=amt))
                        prev = cum
            else:
                prev = 0.0
                tot = est * fac
                for me in month_ends(start, min(end, CUT)):
                    t = (me - start).days / max(1, (end - start).days)
                    cum = round(tot * scurve(t), 2) if me < end else round(tot, 2)
                    amt = round(cum - prev, 2)
                    if amt > 0.5:
                        gl.append(dict(afe_no=afe_no, element_code=k, po_no="", period_end=me, amount_rm=amt))
                    prev = cum
    # seeded supplements on three of the overrun AFEs that started earliest
    over = sorted([a for a in afes if a["_factor"] > 1.15 and a["status"] == "Approved"], key=lambda a: a["planned_start"])[:4]
    for a in over[:3]:
        sup_amt = round(a["amount_rm"] * (a["_factor"] - 1.0) * rng.uniform(0.9, 1.05), -4)
        yr = 2026
        seq[yr] += 1
        sno = f"TSE-AFE-{yr % 100:02d}-{seq[yr]:03d}"
        raised = max(a["decided_on"] + timedelta(days=120), date(2026, 3, 2))
        total = a["amount_rm"] + sup_amt
        tier = tier_for(total)  # LOA on the cumulative approved amount
        fin_at = raised + timedelta(days=rng.randint(1, 4))
        dec = fin_at + timedelta(days={"T1": 3, "T2": 6, "T3": 12}[tier])
        afes.append(dict(afe_no=sno, parent_afe_no=a["afe_no"], kind="Supplement", title=f"Supplement to {a['afe_no']}: {a['title']}",
                         asset_code=a["asset_code"], afe_type=a["afe_type"], requester=a["requester"], raised_on=raised,
                         submitted_on=raised, decided_on=dec, amount_rm=sup_amt, loa_tier=tier, status="Approved",
                         planned_start=a["planned_start"], planned_end=a["planned_end"], _factor=1.0))
        lines.append(dict(afe_no=sno, element_code="CON", estimate_rm=sup_amt))   # contract C3: a supplement is one contingency line
        decisions.append(dict(afe_no=sno, step="Finance check", approver=FIN_CTRL, role="Finance controller", submitted_on=raised,
                              decided_on=fin_at, outcome="Passed", comment="Overrun confirmed by project controls."))
        approver = {"T1": ASSET_MGR[a["asset_code"]], "T2": GM_PROJ, "T3": CEO}[tier]
        decisions.append(dict(afe_no=sno, step="LOA approval", approver=approver, role={"T1": "Asset manager", "T2": "GM Projects", "T3": "CEO"}[tier],
                              submitted_on=fin_at, decided_on=dec, outcome="Approved", comment="Approved."))
    return afes, lines, decisions, phasing, pos, gl


VENDORS = ["Selat Marine Services", "Kuala Fabricators", "Bintang Drilling", "Delta Pipe Supply", "Merbau Engineering",
           "Pantai Logistics", "Tiara Valves and Controls", "Sentosa Instruments", "Arus Subsea", "Puncak IT Solutions"]


def frames():
    """All generator outputs as DataFrames (used by main and by the Fabric ERP notebook)."""
    global rng
    rng = random.Random(SEED)
    afes, lines, decisions, phasing, pos, gl = build()
    A = pd.DataFrame(afes).drop(columns=["_factor"])
    L, D, PH, P, G = map(pd.DataFrame, (lines, decisions, phasing, pos, gl))
    # capex budget (WP&B) per asset and year: planned phasing of approved originals x uplift, plus unallocated
    appr = A[(A.status != "Rejected") & (A.kind == "Original")].afe_no
    ph = PH[PH.afe_no.isin(appr)].merge(A[["afe_no", "asset_code"]], on="afe_no").groupby(["asset_code", "year"]).planned_rm.sum()
    B = [dict(asset_code=a, year=y, budget_rm=round(v * rng.uniform(1.04, 1.12), -5)) for (a, y), v in ph.items() if 2024 <= y <= 2026]
    B = pd.DataFrame(B)
    AS = pd.DataFrame([dict(asset_code=a, asset_name=n, asset_kind=k, asset_manager=ASSET_MGR[a]) for a, n, k in ASSETS])
    E = pd.DataFrame([dict(element_code=c, element_name=n, procured_by_po=p) for c, n, p in ELEMENTS])
    LT = pd.DataFrame([dict(tier_code=c, approver_role=r, lower_rm=lo, upper_rm=hi if hi else "") for c, r, lo, hi in LOA])
    return dict(afe=A, afe_line=L, afe_decision=D, afe_phasing=PH, po=P, gl_actual=G, capex_budget=B, dim_asset=AS, dim_cost_element=E, loa_tier=LT)


def control_totals(F):
    A, L, D, P, G, B = F["afe"], F["afe_line"], F["afe_decision"], F["po"], F["gl_actual"], F["capex_budget"]
    return {
        "seed": SEED, "data_cut": str(CUT),
        "afe_rows": len(A), "afe_by_status": A.status.value_counts().sort_index().to_dict(),
        "afe_by_kind": A.kind.value_counts().sort_index().to_dict(),
        "approved_amount_rm": round(float(A[A.status != "Rejected"].amount_rm.sum()), 2),
        "afe_line_rows": len(L), "estimate_rm": round(float(L.estimate_rm.sum()), 2),
        "decision_rows": len(D), "po_rows": len(P), "po_value_rm": round(float(P.po_value_rm.sum()), 2),
        "gl_rows": len(G), "gl_amount_rm": round(float(G.amount_rm.sum()), 2),
        "budget_rows": len(B), "budget_rm": round(float(B.budget_rm.sum()), 2),
    }


def main():
    F = frames()
    os.makedirs(OUT, exist_ok=True)
    for name, df in F.items():
        df.to_csv(f"{OUT}/{name}.csv", index=False)
    ct = control_totals(F)
    json.dump(ct, open(f"{OUT}/control_totals.json", "w"), indent=1, default=str)
    print(json.dumps(ct, indent=1, default=str))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************


import json, time, traceback
import pandas as pd
from pyspark.sql import functions as F
spark.conf.set("spark.sql.session.timeZone", "UTC")

def write_table(name, pdf):
    if len(pdf) == 0:   # an empty frame has no rows to infer a schema from (gold_waiting before live requests)
        from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType, TimestampType, BooleanType
        mp = {"int64": LongType(), "float64": DoubleType(), "bool": BooleanType(), "datetime64[ns]": TimestampType()}
        sdf = spark.createDataFrame([], StructType([StructField(c, mp.get(str(t), StringType()), True) for c, t in pdf.dtypes.items()]))
    else:
        sdf = spark.createDataFrame(pdf)
    for c, t in sdf.dtypes:
        if t in ("double", "float"):
            sdf = sdf.withColumn(c, F.when(F.isnan(F.col(c)), F.lit(None)).otherwise(F.col(c)))
    sdf.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(name)
    return spark.read.table(name).count()

def finish(R):
    # A verdict that is not *_OK fails the run (S279); the pipeline gate is the second check
    if not str(R.get("verdict", "")).endswith("_OK"):
        raise RuntimeError(json.dumps(R, default=str, sort_keys=True)[:4000])
    notebookutils.notebook.exit(json.dumps(R, default=str, sort_keys=True))

EXPECTED = {"afe_rows": 63, "afe_line_rows": 314, "decision_rows": 132, "po_rows": 455, "po_value_rm": 678909900.0, "gl_rows": 4718, "gl_amount_rm": 584437639.23, "budget_rows": 15, "budget_rm": 785600000.0}
R = {"verdict": "ERP_START"}
try:
    Fr = frames(); ct = control_totals(Fr)
    bad = {k: [ct[k], v] for k, v in EXPECTED.items() if ct[k] != v}
    if bad:
        R = {"verdict": "ERP_CONTROL_MISMATCH", "bad": bad}
    else:
        rb = {}
        for src, dst in (("po", "bronze_po"), ("gl_actual", "bronze_gl"), ("capex_budget", "bronze_budget"), ("dim_cost_element", "bronze_element")):
            df = Fr[src].copy()
            for c in ("period_end", "awarded_on"):
                if c in df.columns: df[c] = pd.to_datetime(df[c])
            rb[dst] = write_table(dst, df)
        gl_sum = round(float(spark.read.table("bronze_gl").agg(F.sum("amount_rm")).first()[0]), 2)
        ok = rb["bronze_po"] == ct["po_rows"] and rb["bronze_gl"] == ct["gl_rows"] and abs(gl_sum - ct["gl_amount_rm"]) < 0.005
        R = {"verdict": "ERP_OK" if ok else "ERP_READBACK_MISMATCH", "readback": rb, "gl_sum": gl_sum, "control": {k: ct[k] for k in EXPECTED}}
except Exception as e:
    R = {"verdict": "ERP_FAILED", "error": str(e)[:1200], "tb": traceback.format_exc()[-1500:]}
finish(R)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
