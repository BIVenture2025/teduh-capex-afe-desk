#!/usr/bin/env python3
# P38 (Teduh Samudera, Capex AFE Desk) - PBIR report generator, 5 pages, 1280 x 720, Direct Lake on SM_TeduhCapex.
# Built to the approved mockup (01_Design/P38_CapexAFE_Package.html, G2 2026-11-24). Primitives: _ENGINE/lib/pbir_kit.py.
# Shape of header, slicers, binding and report.json from P37's delivered build_report.py. Titles are DAX (no typed numbers).
# DEVIATIONS FROM THE MOCKUP (recorded):
#   1. AFE detail is a normal page with an AFE slicer, not a drill-through page: no proven PBIR drill-through shape here.
#   2. The 110% trigger is a second bar series on the detail page and a column in the Watchlist table, not a constant line:
#      no proven PBIR constant-line shape on a bar chart.
#   3. The Approver role slicer filters the step charts and tables (Decision[role]); 'Waiting for a decision' ignores it.
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.environ.get("ENGINE_LIB", os.path.join(HERE, "..", "..", "..", "..", "_ENGINE", "lib"))
sys.path.insert(0, KIT)
import pbir_kit as K  # noqa: E402
K.configure(INK="#1B2A3A", SEC="#5A6B7B", TER="#5A6B7B", CARD_BG="#FFFFFF", BORDER="#EAEFF5", PAGE_BG="#F6F9FC",
            D1="#1F4E79", D2="#2C7F8C", D3="#1B2A3A", D4="#5E86AE", D5="#C0492F",
            MILLIONS={"Open approved", "Open committed", "Open EAC", "Open headroom", "Over approval", "Approved", "Actual to date", "Open commitment",
                      "Committed", "EAC", "Headroom", "Actual", "Cumulative actual", "Budget", "Budget to date", "Estimate", "PO value", "Invoiced", "Planned"})
from pbir_kit import (SCHEMA, b, s, pos, textbox, nav, rule, kpi_card, chart, table_ex, takeaway, slicer, measure, column, by_measure, by_column, write_json, cat_filter)  # noqa: E402
sys.path.insert(0, HERE)
import build_model as BM  # noqa: E402
REPORT_NAME, MODEL_FOLDER, THEME_FILE = "P38_TeduhCapex", "SM_TeduhCapex.SemanticModel", "PitchSidePro_Theme_v2_Executive.json"
INK, SEC, D1, D2, D3, D4, D5, BORDER = K.INK, K.SEC, K.D1, K.D2, K.D3, K.D4, K.D5, K.BORDER
ST, A, GL, BU, DE, WA, DA, AS, CE, TI, PO, ES, PH, DI = "AFE status", "AFE", "GL", "Budget", "Decision", "Waiting", "Date", "Asset", "Cost element", "Tier", "PO", "Estimate", "Phasing", "Dictionary"
_COLS = {(t, c) for t, (_, _, cols) in BM.TABLES.items() for c, _, _ in cols}
_MEAS = {(t, n) for t, n, *_ in BM.MEAS}
USED = []
def M(e, n, d=None): USED.append(("m", e, n)); return measure(e, n, d)
def C(e, p, d=None): USED.append(("c", e, p)); return column(e, p, d)
def KM(e, n, l=None): USED.append(("m", e, n)); return (e, n, l) if l else (e, n)
def T(name, p, e, prop, **kw): USED.append(("m", e, prop)); return takeaway(name, p, e, prop, **kw)
TOP = 148
def header(title, tmeasure=None, t_entity=None, sub_text=None):
    v = [textbox("Title", pos(24, 2, 520, 42, 3000, 100), [(title, 18, INK, True, False)]), nav("Nav", pos(548, 10, 708, 32, 6000, 300)),
         rule("Rule", pos(24, 86, 1232, 2, 5000, 400)),
         T("Disc", pos(18, 686, 1238, 30, 8000, 9000), ST, "Disclaimer", size=9, colr=SEC, alt="Footer: fictional company, synthetic data, the data cut and units, read from the data.")]
    v.append(T("Take", pos(18, 44, 1238, 40, 2000, 200), t_entity, tmeasure, size=12) if tmeasure else textbox("Take", pos(24, 48, 1000, 30, 2000, 200), [(sub_text, 12, SEC, False, False)]))
    return v
def slicer_row(spec):
    v = []
    for i, (lbl, ent, prop, x, lw, sw, alt) in enumerate(spec):
        v.append(textbox("SlLbl%d" % i, pos(x, 104, lw, 24, 7050 + i, 490 + i), [(lbl, 10, SEC, True, False)]))
        USED.append(("c", ent, prop)); v.append(slicer("Sl%d" % i, pos(x + lw, 92, sw, 48, 7100 + i, 500 + i), ent, prop, alt))
    return v
OPEN = lambda n: cat_filter(n, A, "status", ["Approved"])
def default_pick(v, name, ent, prop, literal):
    """Saved slicer selection (S066, component slicer_default_selection.json): objects.general[0].properties.filter.filter."""
    for x in v:
        if x.get("name") == name:
            cond = {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": prop}}],
                           "Values": [[{"Literal": {"Value": literal}}]]}}
            x["visual"]["objects"]["general"] = [{"properties": {"filter": {"filter": {"Version": 2, "From": [{"Name": "c", "Entity": ent, "Type": 0}],
                                                                                    "Where": [{"Condition": cond}]}}}}]
            return v
    raise KeyError(name)

def page_score():
    v = header("Capex scoreboard", "Title scoreboard", ST)
    v += slicer_row([("Year", DA, "year", 24, 50, 140, "Slicer: year for budget and actual."), ("Asset", AS, "asset_name", 240, 56, 220, "Slicer: asset.")])
    default_pick(v, "Sl0", DA, "year", "2026L")   # data-cut year; Year = All mixed years (render check 24 Nov)
    v.append(T("Sub", pos(540, 96, 716, 40, 2100, 210), ST, "Subtitle scoreboard", size=11))   # x 540: clear of the Asset slicer (ends 516), render check 24 Nov
    v.append(kpi_card("Kpi", pos(24, TOP, 1232, 84, 7000, 600),
                      [KM(BU, "Budget", "Capex budget"), KM(GL, "Actual", "Actual in the year"), KM(ST, "Open approved", "Approved, open AFEs"),
                       KM(ST, "Open committed", "Committed, open AFEs"), KM(ST, "Open EAC", "EAC, open AFEs"), KM(ST, "AFEs needing a supplement", "Need a supplement")],
                      "Scoreboard KPI row: budget and actual for the year; approved, committed and EAC of open AFEs; AFEs needing a supplement.", vsize=18))
    v.append(chart("Cum", "lineChart", pos(24, 244, 600, 432, 1100, 700), C(DA, "month_label", "Month"),
                   [M(GL, "Cumulative actual", "Actual"), M(BU, "Budget to date", "Budget, straight line")],
                   "Actual against budget", "Cumulative GL actual by month against the straight-line WP&B budget",
                   "Line chart of cumulative actual against the straight-line budget by month for the selected year.",
                   colors=[D1, D4], legend=True, labels=False, value_axis=True, sort=by_column(DA, "month_date")))
    v.append(table_ex("ByAsset", pos(636, 244, 620, 432, 1200, 710),
                      [C(AS, "asset_name", "Asset"), M(BU, "Budget"), M(GL, "Actual", "Actual YTD"), M(ST, "Open approved", "Approved"),
                       M(ST, "Open committed", "Committed"), M(ST, "Open EAC", "EAC"), M(ST, "AFEs needing a supplement", "Flagged")],
                      "By asset", "Budget and actual follow the Year slicer; approved, committed and EAC are open AFEs to date",
                      "Table by asset: budget, actual, and the open AFEs' approved, committed, EAC and flagged count.", sort=by_measure(BU, "Budget")))
    return v

def page_watch():
    v = header("Watchlist", "Title watchlist", ST)
    v.append(textbox("AsAt", pos(24, 100, 600, 30, 2050, 450), [("Open AFEs as at the data cut; no year filter on this page.", 11, SEC, False, False)]))
    v.append(chart("Pct", "clusteredBarChart", pos(24, TOP, 520, 528, 1100, 700), C(A, "afe_no", "AFE"), [M(ST, "EAC vs approval", "EAC % of approval"), M(ST, "Trigger 110%", "Supplement trigger")],
                   "EAC as a share of approval", "Open AFEs, highest first; the paler bar beside each is the 110% trigger",
                   "Bar chart of EAC as a share of approval for open AFEs, with the 110% trigger beside each bar.",
                   colors=[D5, D4], legend=True, sort=by_measure(ST, "EAC vs approval"), filters=[OPEN("fOpenW1")], margin=30))
    v.append(table_ex("Watch", pos(556, TOP, 700, 528, 1200, 710),
                      [C(A, "afe_no", "AFE"), C(A, "title", "Title"), C(A, "requester", "Owner"), M(ST, "Approved"), M(ST, "Committed"), M(ST, "EAC"),
                       M(ST, "Headroom"), M(ST, "EAC vs approval", "EAC %")],
                      "Watchlist", "Headroom = approved minus actual minus open commitment; pick an AFE on the AFE detail page",
                      "Table of open AFEs with approved, committed, EAC, headroom and EAC as a share of approval, highest share first.",
                      sort=by_measure(ST, "EAC vs approval"), filters=[OPEN("fOpenW2")]))
    return v

def page_appr():
    v = header("Approvals", "Title approvals", DE)
    v += slicer_row([("Year", DA, "year", 24, 50, 140, "Slicer: year of the decision."), ("Approver role", DE, "role", 240, 110, 220, "Slicer: approver role.")])
    v.append(kpi_card("Kpi", pos(24, TOP, 1232, 84, 7000, 600),
                      [KM(DE, "Median submit to decision", "Median days, submit to decision"), KM(DE, "Returned", "Returned by finance"),
                       KM(DE, "Rejected", "Rejected"), KM(WA, "Waiting for a decision", "Waiting for a decision")],
                      "Approvals KPI row: median days from submit to decision, returned, rejected, waiting now.", vsize=18))
    v.append(chart("Steps", "barChart", pos(24, 244, 600, 230, 1100, 700), C(TI, "approver_role", "Tier"),
                   [M(DE, "Finance days per request", "Finance check"), M(DE, "LOA days per request", "LOA approval")],
                   "Days in each step, by tier", "Mean days per request; a returned request counts its finance days twice",
                   "Stacked bar chart of mean days per request in the finance check and at the LOA approver, by tier.", colors=[D4, D1], legend=True,
                   sort=by_column(TI, "approver_role")))
    v.append(table_ex("ByTier", pos(24, 484, 600, 192, 1200, 710),
                      [C(DE, "request_tier", "Tier"), M(DE, "Requests"), M(DE, "Finance days per request", "Finance"), M(DE, "LOA days per request", "LOA"),
                       M(DE, "Submit to decision")], "By tier", "Requests = originals and supplements",
                      "Table by tier: requests, mean finance and LOA days, mean days submit to decision.", sort=by_column(DE, "request_tier")))
    v.append(table_ex("Wait", pos(636, 244, 620, 432, 1300, 720),
                      [C(WA, "afe_no", "AFE"), C(WA, "title", "Title"), C(WA, "with_role", "With"), C(WA, "amount_rm", "Amount RM"), M(WA, "Days waiting", "Days")],
                      "Waiting for a decision", "Who has each open request and for how many days",
                      "Table of requests waiting for a decision, with who has each one and for how many days.", sort=by_measure(WA, "Days waiting")))
    return v

def page_detail():
    v = header("AFE detail", "Title detail", A)
    v += slicer_row([("AFE", A, "afe_no", 24, 40, 220, "Slicer: pick one AFE.")])
    default_pick(v, "Sl0", A, "afe_no", "'TSE-AFE-26-009'")   # opens on the flagged AFE the story follows
    v.append(kpi_card("Kpi", pos(24, TOP, 1232, 84, 7000, 600),
                      [KM(ST, "Approved"), KM(ST, "Actual to date"), KM(ST, "Open commitment"), KM(ST, "EAC"), KM(ST, "Headroom"), KM(ST, "EAC vs approval", "EAC % of approval")],
                      "AFE detail KPI row: approved, actual, open commitment, EAC, headroom and EAC as a share of approval.", vsize=18))
    v.append(table_ex("Elem", pos(24, 244, 410, 230, 1100, 700), [C(CE, "element_name", "Element"), M(ES, "Estimate"), M(PO, "PO value"), M(GL, "Actual")],
                      "By cost element", "Estimate from the AFE; PO value and actual from the ERP extracts",
                      "Table by cost element: estimate, PO value and actual.", sort=by_measure(ES, "Estimate")))
    v.append(table_ex("Dec", pos(24, 484, 410, 192, 1200, 710), [C(DE, "afe_no", "Request"), C(DE, "step", "Step"), C(DE, "role", "Role"), C(DE, "decided_on", "Decided"), C(DE, "outcome", "Outcome")],
                      "Approval history (family)", "Original and any supplements", "Table of the family's decision steps.", sort=by_column(DE, "decided_on")))
    v.append(chart("Spend", "clusteredBarChart", pos(446, 244, 400, 230, 1300, 720), C(A, "afe_no", "AFE"),
                   [M(ST, "Approved"), M(ST, "Actual to date", "Actual"), M(ST, "Committed"), M(ST, "EAC")],
                   "Spend against approval", "Committed = actual plus open POs", "Clustered bars: approved, actual, committed and EAC for the AFE.",
                   colors=[D4, D1, D3, D5], legend=True))
    v.append(chart("Phase", "clusteredColumnChart", pos(446, 484, 400, 192, 1400, 730), C(DA, "year", "Year"), [M(PH, "Planned"), M(GL, "Actual")],
                   "Phasing by year", "Planned phasing against GL actual", "Columns: planned and actual by year for the AFE.", colors=[D4, D1], legend=True,
                   sort=by_column(DA, "year")))
    v.append(table_ex("POs", pos(858, 244, 398, 432, 1500, 740), [C(PO, "po_no", "PO"), C(PO, "vendor", "Vendor"), M(PO, "PO value", "Value"), M(PO, "Invoiced")],
                      "Purchase orders", "Largest first", "Table of the AFE's purchase orders, largest first.", sort=by_measure(PO, "PO value")))
    return v

def page_guide():
    v = header("Report guide", sub_text="Terms, sources and the data dictionary")
    p = lambda t, sz=11, c=INK, bold=False: (t, sz, c, bold, False)
    v.append(textbox("Read", pos(24, 100, 600, 400, 1100, 600), [
        p("Words used in this report", 14, INK, True),
        p("AFE: authority for expenditure, the approval to spend capital on one project, with its estimate by cost element."),
        p("Supplement: a supplementary AFE that raises the approved amount of an original AFE. It adds approval, not estimate."),
        p("LOA: limits of authority. Finance checks every AFE first; then the asset manager (up to RM 5m), GM Projects (up to RM 25m) or the CEO, on the AFE total including supplements."),
        p("Committed: actual cost booked plus purchase orders not yet invoiced."),
        p("EAC: estimate at completion: committed cost plus the remaining estimate, scaled by how awards are running against estimate. Contingency is not counted."),
        p("Headroom: approved minus committed. A supplement is flagged when EAC passes 110% of approval."),
        p("WP&B: work programme and budget, the asset's approved annual capex budget.")], panel=True, accent=BORDER))
    v.append(textbox("Src", pos(24, 508, 600, 170, 1300, 620), [
        p("Where the numbers come from", 14, INK, True),
        p("AFEs, lines, phasing and decisions come from the Teduh Capex app (Dataverse) by a Copy job each night. Purchase orders, GL actuals and the capex budget "
          "come from the ERP extract. The notebook NB_TeduhCapex_Gold works out EAC, headroom and the supplement flag; a second Copy job sends them back to the app."),
        p("The data is synthetic, from a seeded generator.", 11, SEC)], panel=True, accent=BORDER))
    v.append(table_ex("Dict", pos(636, 100, 620, 578, 1200, 610), [C(DI, "measure", "Measure"), C(DI, "folder", "Group"), C(DI, "definition", "Definition")],
                      "Data dictionary", "Every measure in the model and what it means", "Table listing every measure, its group and its definition.",
                      sort=by_column(DI, "folder")))
    return v

PAGES = [("PageScore", "Scoreboard", page_score), ("PageWatch", "Watchlist", page_watch), ("PageAppr", "Approvals", page_appr),
         ("PageDetail", "AFE detail", page_detail), ("PageGuide", "Report guide", page_guide)]

def build(out_root, theme_src):
    rep = os.path.join(out_root, REPORT_NAME + ".Report")
    pages = []
    for name, display, fn in PAGES:
        vis = fn(); names = [x["name"] for x in vis]
        assert len(names) == len(set(names)), name
        pages.append((name, display, vis))
    miss = [u for u in USED if (u[0] == "m" and (u[1], u[2]) not in _MEAS) or (u[0] == "c" and (u[1], u[2]) not in _COLS)]
    if miss: raise SystemExit("fields not in the model: %s" % miss)
    write_json(os.path.join(out_root, REPORT_NAME + ".pbip"), {"$schema": SCHEMA["pbip"], "version": "1.0", "artifacts": [{"report": {"path": REPORT_NAME + ".Report"}}], "settings": {"enableAutoRecovery": True}})
    write_json(os.path.join(rep, ".platform"), {"$schema": SCHEMA["platform"], "metadata": {"type": "Report", "displayName": REPORT_NAME,
               "description": "P38 Capex AFE Desk: scoreboard, watchlist, approvals, AFE detail, guide. Direct Lake on SM_TeduhCapex."},
               "config": {"version": "2.0", "logicalId": "38a00000-0000-4000-8000-000000000007"}})
    write_json(os.path.join(rep, "definition.pbir"), {"$schema": SCHEMA["pbir"], "version": "4.0", "datasetReference": {"byPath": {"path": "../" + MODEL_FOLDER}}})
    write_json(os.path.join(rep, "definition", "version.json"), {"$schema": SCHEMA["version"], "version": "2.0.0"})
    theme = json.load(open(theme_src, encoding="utf-8-sig")); theme["name"] = THEME_FILE
    write_json(os.path.join(rep, "StaticResources", "RegisteredResources", THEME_FILE), theme)
    write_json(os.path.join(rep, "definition", "report.json"), {"$schema": SCHEMA["report"],
        "themeCollection": {"customTheme": {"name": THEME_FILE, "reportVersionAtImport": {"visual": "2.11.0", "report": "3.3.0", "page": "2.1.0"}, "type": "RegisteredResources"}},
        "objects": {"section": [{"properties": {"verticalAlignment": s("Top")}}], "outspacePane": [{"properties": {"expanded": b(False)}}]},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": THEME_FILE, "path": THEME_FILE, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}})
    order = [p[0] for p in pages]
    write_json(os.path.join(rep, "definition", "pages", "pages.json"), {"$schema": SCHEMA["pages"], "pageOrder": order, "activePageName": order[0], "landingPageName": order[0]})
    counts = {}
    for name, display, vis in pages:
        pdir = os.path.join(rep, "definition", "pages", name)
        write_json(os.path.join(pdir, "page.json"), {"$schema": SCHEMA["page"], "name": name, "displayName": display, "displayOption": "FitToPage", "height": 720, "width": 1280})
        for x in vis: write_json(os.path.join(pdir, "visuals", x["name"], "visual.json"), x)
        counts[name] = len(vis)
    return rep, counts

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "estate", "fabric")
    theme_src = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "..", "..", "..", "Themes", THEME_FILE)
    rep, counts = build(out, theme_src)
    print("[scan] built %s (%d files)" % (rep, sum(len(f) for _, _, f in os.walk(rep))), counts, "fields checked", len(USED))
