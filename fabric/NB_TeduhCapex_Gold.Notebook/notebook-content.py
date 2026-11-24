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

# NB_TeduhCapex_Gold (P38)
#
# Silver and Gold from Bronze; EAC contract C1-C9; outbound tables for CJ_Status_Out. Seed families must equal the frozen oracle to the cent. Exits with a verdict JSON.

# CELL ********************

# gold_module.py - P38 Gold: Silver and Gold tables from Bronze (Dataverse copy + ERP extract), the EAC contract C1-C9
# (same gold() as 01_Design/src/oracle.py) and the outbound tables for CJ_Status_Out. Pure pandas; run(T) -> (out, R).
import json, uuid
import pandas as pd

LIVE_STATUS = ("Approved", "Closed")
PENDING = ("Submitted", "Finance check", "LOA approval")
NS = uuid.UUID("38a00000-0000-4000-8000-000000000038")
ROLE = {"T1": "Asset manager", "T2": "GM Projects", "T3": "CEO"}


def gold(A, L, P, G):
    A = A.copy(); G = G.copy()
    A["parent_afe_no"] = A["parent_afe_no"].fillna("")
    A["root"] = A.parent_afe_no.where(A.parent_afe_no != "", A.afe_no)
    orig = A[A.kind == "Original"].set_index("afe_no")
    approved = A[A.status.isin(LIVE_STATUS)].groupby("root").amount_rm.sum()
    est = L[L.afe_no.isin(orig.index) & (L.element_code != "CON")].groupby(["afe_no", "element_code"]).estimate_rm.sum()
    po_e = P.groupby(["afe_no", "element_code"]).po_value_rm.sum()
    G["po_no"] = G["po_no"].fillna("").astype(str); G["amount_rm"] = G.amount_rm.astype(float)
    nonpo = G[G.po_no == ""].groupby(["afe_no", "element_code"]).amount_rm.sum()
    actual = G.groupby("afe_no").amount_rm.sum()
    inv = G[G.po_no != ""].groupby("po_no").amount_rm.sum()
    P = P.copy(); P["open"] = (P.po_value_rm - P.po_no.map(inv).fillna(0)).clip(lower=0)
    open_c = P.groupby("afe_no").open.sum()
    rows = []
    for root, o in orig.iterrows():
        if o.status not in LIVE_STATUS:
            continue
        e = est.loc[root] if root in est.index.get_level_values(0) else pd.Series(dtype=float)
        com = {k: float(po_e.get((root, k), 0.0)) + float(nonpo.get((root, k), 0.0)) for k in e.index}
        q = [k for k in e.index if e[k] > 0 and com[k] >= 0.5 * e[k]]
        f = (sum(com[k] for k in q) / sum(e[k] for k in q)) if q else 1.0
        f = min(max(f, 0.80), 1.50)
        act = round(float(actual.get(root, 0.0)), 2)
        eac = act if o.status == "Closed" else sum(com[k] + max(0.0, e[k] - com[k]) * f for k in e.index)
        appr = float(approved.get(root, 0.0))
        oc = round(float(open_c.get(root, 0.0)), 2)
        rows.append(dict(afe_no=root, asset_code=o.asset_code, afe_type=o.afe_type, status=o.status, approved_rm=round(appr, 2),
                         actual_rm=act, open_commit_rm=oc, committed_total_rm=round(act + oc, 2), award_factor=round(f, 4),
                         eac_rm=round(eac, 2), eac_vs_approved=round(eac / appr, 4) if appr else None,
                         headroom_rm=round(appr - act - oc, 2),
                         supplement_needed=bool(o.status == "Approved" and round(eac, 2) > round(1.10 * appr, 2))))
    return pd.DataFrame(rows)


def _d(s):
    return pd.to_datetime(s, errors="coerce").dt.tz_localize(None) if hasattr(pd.to_datetime(s, errors="coerce"), "dt") else s


def silver(T):
    """Bronze (tsc_ logical names from the Copy job, ERP extract) -> silver frames with the generator's column names."""
    a = T["bronze_afe"]
    A = pd.DataFrame({"afe_no": a.tsc_afeno, "parent_afe_no": a.tsc_parentafeno.fillna(""), "kind": a.tsc_kind, "title": a.tsc_title,
                      "asset_code": a.tsc_assetcode, "afe_type": a.tsc_afetype, "requester": a.tsc_requestername,
                      "requester_email": a.tsc_requesteremail, "amount_rm": a.tsc_amount.astype(float), "status": a.tsc_status,
                      "loa_tier": a.tsc_loatier, "raised_on": _d(a.tsc_raisedon), "submitted_on": _d(a.tsc_submittedon),
                      "decided_on": _d(a.tsc_decidedon), "planned_start": _d(a.tsc_plannedstart), "planned_end": _d(a.tsc_plannedend),
                      "source": a.tsc_source.fillna("Live")})
    A["root_afe_no"] = A.parent_afe_no.where(A.parent_afe_no != "", A.afe_no)
    l = T["bronze_afeline"]; L = pd.DataFrame({"afe_no": l.tsc_afeno, "element_code": l.tsc_elementcode, "estimate_rm": l.tsc_estimate.astype(float)})
    p = T["bronze_afephasing"]; PH = pd.DataFrame({"afe_no": p.tsc_afeno, "year": p.tsc_year.astype(int), "planned_rm": p.tsc_planned.astype(float)})
    d = T["bronze_afedecision"]
    D = pd.DataFrame({"afe_no": d.tsc_afeno, "step": d.tsc_step, "role": d.tsc_role, "approver": d.tsc_approvername,
                      "submitted_on": _d(d.tsc_submittedon), "decided_on": _d(d.tsc_decidedon), "outcome": d.tsc_outcome, "comment": d.tsc_comment})
    D["days"] = (D.decided_on - D.submitted_on).dt.days
    return A, L, PH, D


def run(T, frozen, as_of="2026-10-31", now=None, dictionary=None):
    R = {"verdict": "GOLD_START"}
    A, L, PH, D = silver(T)
    P = T["bronze_po"].copy(); G = T["bronze_gl"].copy(); B = T["bronze_budget"].copy()
    G["po_no"] = G["po_no"].fillna("").astype(str)
    g = gold(A, L, P, G)
    live_roots = set(A[A.source != "Seed"].root_afe_no)
    fz = frozen.set_index("afe_no")
    cols = ["approved_rm", "actual_rm", "open_commit_rm", "eac_rm", "headroom_rm", "award_factor"]
    seed = g[~g.afe_no.isin(live_roots)].set_index("afe_no")
    miss = sorted(set(fz.index) - set(seed.index) - live_roots)
    diffs = []
    for k in seed.index:
        if k not in fz.index:
            diffs.append([k, "not in oracle"]); continue
        for c in cols:
            if abs(float(seed.at[k, c]) - float(fz.at[k, c])) > 0.005:
                diffs.append([k, c, float(seed.at[k, c]), float(fz.at[k, c])])
        if bool(seed.at[k, "supplement_needed"]) != bool(fz.at[k, "supplement_needed"]):
            diffs.append([k, "flag"])
    R.update(families=len(g), seed_checked=len(seed), seed_diffs=diffs[:20], seed_missing=miss, live_families=sorted(live_roots),
             flagged=int(g.supplement_needed.sum()), open=int((g.status == "Approved").sum()))
    # Gold tables
    out = {}
    out["dim_afe"] = A[A.kind == "Original"][["afe_no", "title", "asset_code", "afe_type", "status", "requester", "loa_tier", "planned_start", "planned_end", "source"]].rename(columns={"loa_tier": "original_tier"})
    G["month_date"] = pd.to_datetime(G.period_end).dt.to_period("M").dt.to_timestamp()
    out["fact_gl"] = G.assign(root_afe_no=G.afe_no)[["afe_no", "root_afe_no", "element_code", "po_no", "month_date", "amount_rm"]]
    inv = G[G.po_no != ""].groupby("po_no").amount_rm.sum()
    P["invoiced_rm"] = P.po_no.map(inv).fillna(0.0).round(2); P["open_rm"] = (P.po_value_rm - P.invoiced_rm).clip(lower=0).round(2)
    out["fact_po"] = P.assign(root_afe_no=P.afe_no, awarded_on=pd.to_datetime(P.awarded_on))[["po_no", "afe_no", "root_afe_no", "element_code", "vendor", "awarded_on", "po_value_rm", "invoiced_rm", "open_rm"]]
    orig_nos = set(A[A.kind == "Original"].afe_no)
    out["fact_estimate"] = L[L.afe_no.isin(orig_nos)].assign(root_afe_no=lambda x: x.afe_no)[["afe_no", "root_afe_no", "element_code", "estimate_rm"]]
    out["fact_phasing"] = PH.merge(A[["afe_no", "root_afe_no"]], on="afe_no").assign(year_date=lambda x: pd.to_datetime(x.year.astype(str) + "-01-01"))[["afe_no", "root_afe_no", "year", "year_date", "planned_rm"]]
    out["fact_budget"] = B.assign(year_date=pd.to_datetime(B.year.astype(str) + "-01-01"))[["asset_code", "year", "year_date", "budget_rm"]]
    fd = D.merge(A[["afe_no", "root_afe_no", "loa_tier", "kind", "asset_code"]], on="afe_no", how="left").rename(columns={"loa_tier": "request_tier"})
    fd["decided_month"] = fd.decided_on.dt.to_period("M").dt.to_timestamp()
    out["fact_decision"] = fd
    out["gold_afe_status"] = g.rename(columns={"afe_no": "root_afe_no"})
    # waiting requests (live)
    now = pd.Timestamp(now or pd.Timestamp.utcnow().tz_localize(None).normalize())
    w = A[A.status.isin(PENDING)].copy()
    last = D.groupby("afe_no").submitted_on.max()
    w["with_role"] = w.apply(lambda r: "Finance controller" if r.status in ("Submitted", "Finance check") else ROLE.get(r.loa_tier, "Approver"), axis=1)
    w["days_waiting"] = (now - w.afe_no.map(last).fillna(w.submitted_on)).dt.days
    out["gold_waiting"] = w[["afe_no", "root_afe_no", "title", "kind", "asset_code", "amount_rm", "status", "with_role", "days_waiting"]]
    # dims
    out["dim_date"] = pd.DataFrame({"month_date": pd.date_range("2024-01-01", "2028-12-01", freq="MS")}).assign(
        year=lambda x: x.month_date.dt.year, month_no=lambda x: x.month_date.dt.month, month_label=lambda x: x.month_date.dt.strftime("%b %Y"))
    out["dim_asset"] = T["bronze_asset"].rename(columns={"tsc_assetcode": "asset_code", "tsc_assetname": "asset_name", "tsc_assetkind": "asset_kind", "tsc_assetmanager": "asset_manager"})[["asset_code", "asset_name", "asset_kind", "asset_manager"]]
    out["dim_cost_element"] = T["bronze_element"][["element_code", "element_name", "procured_by_po"]]
    if dictionary is not None:
        out["dictionary"] = pd.DataFrame(dictionary)[["measure", "folder", "definition"]]
    out["dim_tier"] = pd.DataFrame([dict(tier=t, approver_role=r, sort=i) for i, (t, r) in enumerate(ROLE.items(), 1)])
    # outbound to Dataverse (GUID upsert, S164)
    ts = pd.Timestamp.utcnow().tz_localize(None).floor("s")
    o = g.copy()
    out["gold_afe_status_out"] = pd.DataFrame({"tsc_afestatusid": [str(uuid.uuid5(NS, "afestatus/" + k)) for k in o.afe_no], "tsc_afeno": o.afe_no,
        "tsc_approved": o.approved_rm, "tsc_actual": o.actual_rm, "tsc_opencommit": o.open_commit_rm, "tsc_committed": o.committed_total_rm,
        "tsc_eac": o.eac_rm, "tsc_eacpct": o.eac_vs_approved, "tsc_headroom": o.headroom_rm, "tsc_supplementneeded": o.supplement_needed,
        "tsc_assetcode": o.asset_code, "tsc_status": o.status, "tsc_refreshedon": ts})
    yr = int(str(as_of)[:4])
    ga = out["fact_gl"].merge(A[["afe_no", "asset_code"]], on="afe_no")
    ab = []
    for r in B.itertuples():
        act = float(ga[(ga.asset_code == r.asset_code) & (ga.month_date.dt.year == r.year)].amount_rm.sum())
        apy = float(A[(A.asset_code == r.asset_code) & A.status.isin(LIVE_STATUS) & (A.decided_on.dt.year == r.year)].amount_rm.sum())
        ab.append(dict(tsc_assetbudgetid=str(uuid.uuid5(NS, "assetbudget/%s/%s" % (r.asset_code, r.year))), tsc_name="%s %s" % (r.asset_code, r.year),
                       tsc_assetcode=r.asset_code, tsc_year=int(r.year), tsc_budget=float(r.budget_rm), tsc_actual=round(act, 2),
                       tsc_approvedinyear=round(apy, 2), tsc_left=round(float(r.budget_rm) - act, 2), tsc_refreshedon=ts))
    out["gold_asset_budget_out"] = pd.DataFrame(ab)
    ok = not diffs and not miss and len(seed) > 0
    R["verdict"] = "GOLD_OK" if ok else "GOLD_SEED_MISMATCH"
    R["rows"] = {k: len(v) for k, v in out.items()}
    return out, R

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

import io
FROZEN = pd.read_csv(io.StringIO("""afe_no,asset_code,afe_type,status,approved_rm,actual_rm,open_commit_rm,committed_total_rm,award_factor,eac_rm,eac_vs_approved,headroom_rm,supplement_needed
TSE-AFE-24-001,CORP,IT and buildings,Closed,3120000.0,2637358.49,0.0,2637358.49,0.9392,2637358.49,0.8453,482641.51,False
TSE-AFE-24-002,TS,Study,Closed,2490000.0,2081963.86,0.0,2081963.86,0.929,2081963.86,0.8361,408036.14,False
TSE-AFE-24-004,TU,Facilities,Closed,23880000.0,20960172.91,0.0,20960172.91,0.9753,20960172.91,0.8777,2919827.09,False
TSE-AFE-24-005,TT,Facilities,Approved,20140000.0,17877809.69,0.0,17877809.69,0.9863,18212167.93,0.9043,2262190.31,False
TSE-AFE-24-006,OGT,IT and buildings,Closed,1890000.0,1750206.66,0.0,1750206.66,1.0289,1750206.66,0.926,139793.34,False
TSE-AFE-24-007,TU,Pipeline,Closed,20550000.0,16842488.48,0.26,16842488.74,0.9107,16842488.48,0.8196,3707511.26,False
TSE-AFE-24-008,CORP,IT and buildings,Closed,2240000.0,1896483.72,0.0,1896483.72,0.9407,1896483.72,0.8466,343516.28,False
TSE-AFE-24-009,TS,Drilling,Closed,73100000.0,55307976.73,0.0,55307976.73,0.8407,55307976.73,0.7566,17792023.27,False
TSE-AFE-24-010,OGT,Study,Closed,1120000.0,899063.66,0.0,899063.66,0.8919,899063.66,0.8027,220936.34,False
TSE-AFE-24-011,TS,Facilities,Approved,22490000.0,19824361.36,0.0,19824361.36,1.3439,19824361.36,0.8815,2665638.64,False
TSE-AFE-24-012,TS,Pipeline,Closed,24680000.0,22074381.11,0.0,22074381.11,0.9938,22074381.11,0.8944,2605618.89,False
TSE-AFE-24-013,OGT,IT and buildings,Closed,940000.0,852670.86,0.0,852670.86,1.0079,852670.86,0.9071,87329.14,False
TSE-AFE-24-014,OGT,Study,Closed,2440000.0,2185221.99,0.0,2185221.99,0.9951,2185221.99,0.8956,254778.01,False
TSE-AFE-24-015,OGT,Facilities,Closed,20010000.0,16997242.31,0.25,16997242.56,0.9438,16997242.31,0.8494,3012757.44,False
TSE-AFE-24-016,TT,Pipeline,Approved,22270000.0,19934703.54,487.61,19935191.15,1.3424,19935191.15,0.8952,2334808.85,False
TSE-AFE-24-017,TS,Drilling,Closed,58210000.0,51575920.51,0.0,51575920.51,0.9845,51575920.51,0.886,6634079.49,False
TSE-AFE-24-018,TT,Facilities,Closed,21700000.0,19192775.49,0.0,19192775.49,0.9827,19192775.49,0.8845,2507224.51,False
TSE-AFE-24-019,OGT,Facilities,Closed,26850000.0,20702600.28,0.0,20702600.28,0.8567,20702600.28,0.771,6147399.72,False
TSE-AFE-24-020,CORP,IT and buildings,Closed,3560000.0,2903466.12,0.0,2903466.12,0.9062,2903466.12,0.8156,656533.88,False
TSE-AFE-25-001,CORP,IT and buildings,Approved,660000.0,821797.31,0.0,821797.31,1.3835,821797.31,1.2451,-161797.31,True
TSE-AFE-25-002,CORP,Study,Closed,2150000.0,1755794.75,0.0,1755794.75,0.9074,1755794.75,0.8166,394205.25,False
TSE-AFE-25-003,CORP,IT and buildings,Closed,3020000.0,2502713.83,0.0,2502713.83,0.9208,2502713.83,0.8287,517286.17,False
TSE-AFE-25-004,OGT,Facilities,Approved,9270000.0,7904929.63,0.0,7904929.63,0.9475,8319998.0,0.8975,1365070.37,False
TSE-AFE-25-005,CORP,Study,Closed,1750000.0,1435574.82,0.0,1435574.82,0.9115,1435574.82,0.8203,314425.18,False
TSE-AFE-25-006,TS,Pipeline,Approved,55150000.0,49378222.77,474911.19,49853133.96,1.2465,49853133.96,0.904,5296866.04,False
TSE-AFE-25-007,OGT,Study,Closed,1680000.0,1478236.51,0.0,1478236.51,0.9777,1478236.51,0.8799,201763.49,False
TSE-AFE-25-008,CORP,IT and buildings,Closed,2770000.0,2229482.37,0.0,2229482.37,0.8943,2229482.37,0.8049,540517.63,False
TSE-AFE-25-009,CORP,IT and buildings,Approved,2920000.0,2514744.69,0.0,2514744.69,0.9569,2625798.52,0.8992,405255.31,False
TSE-AFE-25-010,TT,Facilities,Approved,16970000.0,10550090.55,2847983.04,13398073.59,0.8772,15042832.45,0.8864,3571926.41,False
TSE-AFE-25-011,OGT,Pipeline,Approved,25170000.0,10560256.5,11425162.47,21985418.97,0.9705,22680300.13,0.9011,3184581.03,False
TSE-AFE-25-012,TS,Drilling,Approved,68230000.0,60435418.83,8580.56,60443999.39,0.9843,61424774.19,0.9003,7786000.61,False
TSE-AFE-25-013,TS,Facilities,Approved,6940000.0,4539649.67,1589401.57,6129051.24,0.9813,6282080.05,0.9052,810948.76,False
TSE-AFE-25-014,TU,Study,Closed,1430000.0,1353211.96,0.0,1353211.96,1.0514,1353211.96,0.9463,76788.04,False
TSE-AFE-25-015,OGT,Study,Approved,2990000.0,2543164.61,0.0,2543164.61,0.9451,2682878.37,0.8973,446835.39,False
TSE-AFE-25-016,TT,Study,Closed,2030000.0,1785577.02,0.0,1785577.02,0.9773,1785577.02,0.8796,244422.98,False
TSE-AFE-25-017,TS,Drilling,Closed,38580000.0,33954308.34,0.0,33954308.34,0.9779,33954308.34,0.8801,4625691.66,False
TSE-AFE-25-018,TS,Drilling,Closed,42770000.0,33717532.03,0.0,33717532.03,0.8759,33717532.03,0.7883,9052467.97,False
TSE-AFE-25-019,TT,Facilities,Approved,8910000.0,5797211.75,2015004.12,7812215.87,0.9742,8059942.83,0.9046,1097784.13,False
TSE-AFE-25-020,OGT,Facilities,Approved,21610000.0,7562553.58,9700579.29,17263132.87,0.9256,19286293.52,0.8925,4346867.13,False
TSE-AFE-25-021,TS,Facilities,Closed,6250000.0,5795907.54,0.0,5795907.54,1.0304,5795907.54,0.9273,454092.46,False
TSE-AFE-25-022,TU,Study,Closed,810000.0,769518.2,0.0,769518.2,1.0556,769518.2,0.95,40481.8,False
TSE-AFE-26-002,OGT,Facilities,Approved,23780000.0,669904.14,9318374.16,9988278.3,0.8,19732615.66,0.8298,13791721.7,False
TSE-AFE-26-003,TS,Facilities,Approved,3550000.0,1994346.32,953644.36,2947990.68,0.9227,3175903.41,0.8946,602009.32,False
TSE-AFE-26-004,TT,Pipeline,Approved,40930000.0,2740763.28,16451128.0,19191891.28,0.8,33307978.26,0.8138,21738108.72,False
TSE-AFE-26-005,TU,Pipeline,Approved,22380000.0,3475328.84,13376763.51,16852092.35,0.9381,19938479.05,0.8909,5527907.65,False
TSE-AFE-26-006,OGT,IT and buildings,Approved,1460000.0,1052050.05,568254.83,1620304.88,1.2331,1640275.22,1.1235,-160304.88,True
TSE-AFE-26-007,TU,Facilities,Approved,12050000.0,928536.96,3410552.17,4339089.13,0.8,9543817.83,0.792,7710910.87,False
TSE-AFE-26-008,OGT,IT and buildings,Approved,650000.0,19365.48,202798.46,222163.94,0.851,530944.83,0.8168,427836.06,False
TSE-AFE-26-009,TS,Drilling,Approved,66200000.0,22609209.09,56941521.38,79550730.47,1.3751,81455634.23,1.2304,-13350730.47,True
TSE-AFE-26-010,TT,Study,Approved,1670000.0,1846150.89,0.0,1846150.89,1.2283,1846150.89,1.1055,-176150.89,True
TSE-AFE-26-012,CORP,IT and buildings,Approved,3000000.0,2830505.19,0.0,2830505.19,1.0483,2830505.19,0.9435,169494.81,False
TSE-AFE-26-013,TS,Drilling,Approved,25290000.0,61523.33,1660467.34,1721990.67,1.0,22762000.0,0.9,23568009.33,False
TSE-AFE-26-014,CORP,IT and buildings,Approved,520000.0,6869.13,231413.44,238282.57,1.0175,476196.8,0.9158,281717.43,False
TSE-AFE-26-015,TU,Pipeline,Approved,41740000.0,2863.59,0.0,2863.59,1.0,37566000.0,0.9,41737136.41,False
TSE-AFE-26-016,OGT,IT and buildings,Approved,3480000.0,206582.81,1536805.1,1743387.91,0.8,2854277.58,0.8202,1736612.09,False
TSE-AFE-26-017,CORP,IT and buildings,Approved,780000.0,17305.36,152109.62,169414.98,0.8,595483.0,0.7634,610585.02,False
TSE-AFE-26-018,TU,Drilling,Approved,25400000.0,93569.74,1850612.99,1944182.73,1.0,22860000.0,0.9,23455817.27,False"""))
DICT = json.loads(r"""[
 {
  "measure": "Open approved",
  "folder": "Portfolio",
  "definition": "Approved amount (original plus approved supplements) of open AFEs, at the data cut; not sliced by Year."
 },
 {
  "measure": "Open committed",
  "folder": "Portfolio",
  "definition": "Lifetime actual plus open purchase orders of open AFEs."
 },
 {
  "measure": "Open EAC",
  "folder": "Portfolio",
  "definition": "Estimate at completion of open AFEs, computed in Gold (contract C7)."
 },
 {
  "measure": "Open headroom",
  "folder": "Portfolio",
  "definition": "Approved minus actual minus open commitment, open AFEs."
 },
 {
  "measure": "Open AFEs",
  "folder": "Portfolio",
  "definition": "Number of approved AFEs still spending."
 },
 {
  "measure": "EAC % of approval",
  "folder": "Portfolio",
  "definition": "Open EAC over open approved; blank when nothing is approved."
 },
 {
  "measure": "AFEs needing a supplement",
  "folder": "Portfolio",
  "definition": "Open AFEs with EAC more than 110% of approval (contract C9)."
 },
 {
  "measure": "Over approval",
  "folder": "Portfolio",
  "definition": "EAC minus approval, summed over flagged AFEs."
 },
 {
  "measure": "Approved",
  "folder": "AFE",
  "definition": "Approved amount of the AFEs in context (detail page)."
 },
 {
  "measure": "Actual to date",
  "folder": "AFE",
  "definition": "Lifetime actual of the AFEs in context."
 },
 {
  "measure": "Open commitment",
  "folder": "AFE",
  "definition": "Open purchase-order value not yet invoiced."
 },
 {
  "measure": "Committed",
  "folder": "AFE",
  "definition": "Actual plus open purchase orders."
 },
 {
  "measure": "EAC",
  "folder": "AFE",
  "definition": "Estimate at completion of the AFEs in context."
 },
 {
  "measure": "Headroom",
  "folder": "AFE",
  "definition": "Approved minus committed."
 },
 {
  "measure": "EAC vs approval",
  "folder": "AFE",
  "definition": "EAC over approved for the AFEs in context."
 },
 {
  "measure": "Trigger 110%",
  "folder": "AFE",
  "definition": "The supplement trigger line."
 },
 {
  "measure": "Actual",
  "folder": "Spend",
  "definition": "GL actual in the period in context (follows the Year slicer)."
 },
 {
  "measure": "Data cut",
  "folder": "Spend",
  "definition": "Last month with GL actuals."
 },
 {
  "measure": "Cumulative actual",
  "folder": "Spend",
  "definition": "Actual from January of the year in context to the month in context; blank after the data cut."
 },
 {
  "measure": "Budget",
  "folder": "Spend",
  "definition": "Capex budget (WP&B) of the year in context; the month filter is removed (S277: column-scoped)."
 },
 {
  "measure": "Budget to date",
  "folder": "Spend",
  "definition": "Straight-line budget to the month in context."
 },
 {
  "measure": "Actual % of budget",
  "folder": "Spend",
  "definition": "Actual in the period over the year's budget."
 },
 {
  "measure": "Estimate",
  "folder": "AFE",
  "definition": "Original AFE estimate by cost element."
 },
 {
  "measure": "PO value",
  "folder": "AFE",
  "definition": "Purchase-order value."
 },
 {
  "measure": "Invoiced",
  "folder": "AFE",
  "definition": "Invoiced against purchase orders."
 },
 {
  "measure": "POs",
  "folder": "AFE",
  "definition": "Number of purchase orders."
 },
 {
  "measure": "Planned",
  "folder": "AFE",
  "definition": "Planned phasing by year."
 },
 {
  "measure": "Requests",
  "folder": "Approvals",
  "definition": "Requests (originals and supplements) with a decision step."
 },
 {
  "measure": "Finance days per request",
  "folder": "Approvals",
  "definition": "Days in the finance check per request; a returned request counts its finance days twice."
 },
 {
  "measure": "LOA days per request",
  "folder": "Approvals",
  "definition": "Days at the LOA approver per request."
 },
 {
  "measure": "Submit to decision",
  "folder": "Approvals",
  "definition": "Mean days from first submit to the LOA decision, decided requests."
 },
 {
  "measure": "Median submit to decision",
  "folder": "Approvals",
  "definition": "Median of the same."
 },
 {
  "measure": "Returned",
  "folder": "Approvals",
  "definition": "Steps where finance returned the request."
 },
 {
  "measure": "Rejected",
  "folder": "Approvals",
  "definition": "Requests rejected at the LOA step."
 },
 {
  "measure": "Waiting for a decision",
  "folder": "Approvals",
  "definition": "Requests in Submitted, Finance check or LOA approval now."
 },
 {
  "measure": "Days waiting",
  "folder": "Approvals",
  "definition": "Days since the request reached its current step."
 }
]""")
BRONZE = ["bronze_afe", "bronze_afeline", "bronze_afephasing", "bronze_afedecision", "bronze_asset", "bronze_element", "bronze_po", "bronze_gl", "bronze_budget"]
R = {"verdict": "GOLD_START"}
try:
    spark.sql("REFRESH TABLE bronze_afe") if "bronze_afe" in [t.name for t in spark.catalog.listTables()] else None
    T = {n: spark.read.table(n).toPandas() for n in BRONZE}
    out, R = run(T, FROZEN, dictionary=DICT)
    if R["verdict"] == "GOLD_OK":     # a failed check keeps the previous Gold tables
        for n, df in out.items():
            for c in df.columns:
                if df[c].dtype == object and len(df) and df[c].map(type).eq(bool).all(): df[c] = df[c].astype(bool)
        R["readback"] = {n: write_table(n, df) for n, df in out.items()}
        if any(R["readback"][n] != len(out[n]) for n in out):
            R["verdict"] = "GOLD_READBACK_MISMATCH"
except Exception as e:
    R = {"verdict": "GOLD_FAILED", "error": str(e)[:1200], "tb": traceback.format_exc()[-1500:]}
finish(R)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
