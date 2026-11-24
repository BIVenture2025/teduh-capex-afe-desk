"""oracle.py - P38 reference for the Gold logic (EAC, headroom, supplement flag) and the LOA rule. Rev 2 after the audit.

gold() is the SAME function NB_02 runs over the Bronze snapshot (it is copied into the notebook module), so live AFEs are
computed, not compared with a frozen file. The frozen file afe_status_oracle.csv is the seed check: every family with no
live request must equal it to the cent (Build verdict GOLD_OK).

Contract (Implementation Guide, tab Measures):
  C1 family        = an original AFE plus its supplements; key = root afe_no
  C2 in Gold       = families whose ORIGINAL is Approved or Closed; every other status (Draft, Submitted, Finance check,
                     LOA approval, Returned, Rejected, Needs attention) has no status row
  C3 approved_rm   = original amount + supplements with status Approved or Closed; a supplement is one contingency line,
                     so it raises approval and never the element estimates
  C4 committed_e   = PO value on element e + actual not on a PO for e (contingency excluded)
  C5 remaining_e   = max(0, estimate_e - committed_e)   (estimate_e from the ORIGINAL's lines only)
  C6 award_factor  = sum(committed_e)/sum(estimate_e) over elements with committed_e >= 50% of estimate_e, clamped to
                     [0.80, 1.50]; 1.00 when no element qualifies
  C7 eac_rm        = sum over non-contingency e of (committed_e + remaining_e * award_factor); Closed: eac = actual
  C8 open_commit   = sum over POs of max(0, po_value - invoiced on that PO); headroom = approved - actual - open_commit
  C9 supplement    = status Approved and eac_rm > 1.10 * approved_rm (strictly greater; exactly 110% is not flagged)
LOA: tier on approved family + pending supplements of the family (Submitted, Finance check, LOA approval) + this request.
     T1 asset manager: up to RM 5,000,000 · T2 GM Projects: over RM 5m, up to RM 25,000,000 · T3 CEO: over RM 25m.
     A supplement to a Closed or Rejected original is refused by the app and by the flow.
"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "02_Build", "data", "out")
LIVE_STATUS = ("Approved", "Closed")
PENDING = ("Submitted", "Finance check", "LOA approval")


def loa_tier(approved_family, pending_family, request):
    c = round(approved_family + pending_family + request, 2)
    return "T1" if c <= 5_000_000 else ("T2" if c <= 25_000_000 else "T3")


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


def load(data=DATA):
    return (pd.read_csv(f"{data}/afe.csv"), pd.read_csv(f"{data}/afe_line.csv"), pd.read_csv(f"{data}/po.csv"),
            pd.read_csv(f"{data}/gl_actual.csv", keep_default_na=False))


# (approved family, pending supplements of the family, this request, expected tier)
LOA_VECTORS = [
    (0, 0, 400_000, "T1"), (0, 0, 5_000_000, "T1"), (0, 0, 5_000_000.01, "T2"), (0, 0, 24_990_000, "T2"), (0, 0, 25_000_000, "T2"),
    (0, 0, 25_000_000.01, "T3"), (0, 0, 80_000_000, "T3"), (0, 0, 0.01, "T1"),
    (4_000_000, 0, 900_000, "T1"), (4_000_000, 0, 1_000_000, "T1"), (4_000_000, 0, 1_100_000, "T2"),
    (20_000_000, 0, 4_000_000, "T2"), (20_000_000, 0, 6_000_000, "T3"), (30_000_000, 0, 1_000, "T3"),
    (4_000_000, 900_000, 900_000, "T2"),          # two supplements in flight: the second counts the first (no split)
    (3_000_000, 1_500_000, 400_000, "T1"),        # original + approved supplement in 'approved', a pending one, a new one
    (66_200_000, 0, 15_300_000, "T3"),            # the end-to-end supplement on TSE-AFE-26-009
    (4_200_000, 0, 700_000, "T1"),                # a rejected supplement is not in approved or pending
]


def self_test():
    for a, p, r, exp in LOA_VECTORS:
        assert loa_tier(a, p, r) == exp, (a, p, r, exp)
    # EAC boundary and supplement coding on a synthetic family (contract C3, C9)
    A = pd.DataFrame([dict(afe_no="X-1", parent_afe_no="", kind="Original", status="Approved", amount_rm=100.0, asset_code="TU", afe_type="Facilities")])
    L = pd.DataFrame([dict(afe_no="X-1", element_code="MAT", estimate_rm=90.0), dict(afe_no="X-1", element_code="CON", estimate_rm=10.0)])
    G = pd.DataFrame(columns=["afe_no", "element_code", "po_no", "period_end", "amount_rm"])
    for po, flag in ((110.0, False), (110.01, True)):                     # EAC exactly 110% is not flagged; above is
        P = pd.DataFrame([dict(po_no="P1", afe_no="X-1", element_code="MAT", po_value_rm=po)])
        g = gold(A, L, P, G).iloc[0]
        assert g.supplement_needed == flag and g.eac_rm == po, (po, g.to_dict())
    P = pd.DataFrame([dict(po_no="P1", afe_no="X-1", element_code="MAT", po_value_rm=120.0)])
    A2 = pd.concat([A, pd.DataFrame([dict(afe_no="X-2", parent_afe_no="X-1", kind="Supplement", status="Approved", amount_rm=20.0, asset_code="TU", afe_type="Facilities")])])
    L2 = pd.concat([L, pd.DataFrame([dict(afe_no="X-2", element_code="CON", estimate_rm=20.0)])])
    g1, g2 = gold(A, L, P, G).iloc[0], gold(A2, L2, P, G).iloc[0]
    assert g1.eac_rm == g2.eac_rm == 120.0 and g1.supplement_needed and not g2.supplement_needed and g2.approved_rm == 120.0
    # a pending or rejected supplement does not raise approval; every non-live original status yields no row and no error
    for st in ("Submitted", "Rejected", "Returned"):
        A3 = A2.copy(); A3.loc[A3.afe_no == "X-2", "status"] = st
        assert gold(A3, L2, P, G).iloc[0].approved_rm == 100.0
    for st in ("Draft", "Submitted", "Finance check", "LOA approval", "Returned", "Rejected", "Needs attention"):
        A4 = A.copy(); A4["status"] = st
        assert gold(A4, L, P, G).empty, st
    # an AFE with no PO yet: open commitment 0, factor 1.00, EAC = estimate excluding contingency
    g = gold(A, L, pd.DataFrame(columns=["po_no", "afe_no", "element_code", "po_value_rm"]), G).iloc[0]
    assert g.open_commit_rm == 0 and g.award_factor == 1.0 and g.eac_rm == 90.0
    return len(LOA_VECTORS) + 15


if __name__ == "__main__":
    n = self_test()
    g = gold(*load())
    g.to_csv(os.path.join(HERE, "afe_status_oracle.csv"), index=False)
    s = g[g.status == "Approved"]
    print("self-test checks", n, "pass | families", len(g), "open", len(s), "flagged", int(s.supplement_needed.sum()))
