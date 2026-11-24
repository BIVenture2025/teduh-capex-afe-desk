# Offline replay of gold_module.run on Bronze frames shaped like the Copy job output (tsc_ names) - P38 Build check.
import os, sys, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gold_module as gm
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "out")
r = lambda n: pd.read_csv(os.path.join(D, n), keep_default_na=False, na_values=[""])
a = r("afe.csv"); MY = "Siti Aisyah Kamal"
T = {"bronze_afe": pd.DataFrame({"tsc_afeno": a.afe_no, "tsc_parentafeno": a.parent_afe_no, "tsc_kind": a.kind, "tsc_title": a.title, "tsc_assetcode": a.asset_code,
        "tsc_afetype": a.afe_type, "tsc_requestername": a.requester, "tsc_requesteremail": "x", "tsc_amount": a.amount_rm, "tsc_status": a.status,
        "tsc_loatier": a.loa_tier, "tsc_raisedon": a.raised_on, "tsc_submittedon": a.submitted_on, "tsc_decidedon": a.decided_on,
        "tsc_plannedstart": a.planned_start, "tsc_plannedend": a.planned_end, "tsc_source": "Seed"})}
l = r("afe_line.csv"); T["bronze_afeline"] = pd.DataFrame({"tsc_afeno": l.afe_no, "tsc_elementcode": l.element_code, "tsc_estimate": l.estimate_rm})
p = r("afe_phasing.csv"); T["bronze_afephasing"] = pd.DataFrame({"tsc_afeno": p.afe_no, "tsc_year": p.year, "tsc_planned": p.planned_rm})
d = r("afe_decision.csv"); T["bronze_afedecision"] = pd.DataFrame({"tsc_afeno": d.afe_no, "tsc_step": d.step, "tsc_role": d.role, "tsc_approvername": d.approver,
        "tsc_submittedon": d.submitted_on, "tsc_decidedon": d.decided_on, "tsc_outcome": d.outcome, "tsc_comment": d.comment})
s = r("dim_asset.csv"); T["bronze_asset"] = pd.DataFrame({"tsc_assetcode": s.asset_code, "tsc_assetname": s.asset_name, "tsc_assetkind": s.asset_kind, "tsc_assetmanager": s.asset_manager})
T["bronze_element"] = r("dim_cost_element.csv"); T["bronze_po"] = r("po.csv"); T["bronze_gl"] = r("gl_actual.csv"); T["bronze_budget"] = r("capex_budget.csv")
fz = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "afe_status_oracle.csv"))
out, R = gm.run(T, fz, now="2026-11-24")
print(R["verdict"], R["families"], R["seed_checked"], R["flagged"], R["seed_diffs"][:3])
# live supplement on 26-009: flag must clear (T6)
T2 = dict(T)
T2["bronze_afe"] = pd.concat([T["bronze_afe"], pd.DataFrame([dict(tsc_afeno="TSE-AFE-26-023", tsc_parentafeno="TSE-AFE-26-009", tsc_kind="Supplement", tsc_title="Supplement", tsc_assetcode="TS",
        tsc_afetype="Drilling", tsc_requestername=MY, tsc_requesteremail="x", tsc_amount=15300000.0, tsc_status="Approved", tsc_loatier="T3", tsc_raisedon="2026-11-24",
        tsc_submittedon="2026-11-24", tsc_decidedon="2026-11-24", tsc_plannedstart=None, tsc_plannedend=None, tsc_source="Live")])], ignore_index=True)
T2["bronze_afeline"] = pd.concat([T["bronze_afeline"], pd.DataFrame([dict(tsc_afeno="TSE-AFE-26-023", tsc_elementcode="CON", tsc_estimate=15300000.0)])], ignore_index=True)
out2, R2 = gm.run(T2, fz, now="2026-11-24")
g = out2["gold_afe_status"].set_index("root_afe_no").loc["TSE-AFE-26-009"]
print(R2["verdict"], R2["flagged"], R2["live_families"], g.approved_rm, g.eac_vs_approved, g.supplement_needed)
print({k: v for k, v in R["rows"].items()})
assert R["verdict"] == "GOLD_OK" and R2["verdict"] == "GOLD_OK" and R2["flagged"] == 3 and not g.supplement_needed
print("REPLAY PASS")
