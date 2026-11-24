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
