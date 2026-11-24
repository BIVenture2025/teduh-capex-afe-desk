"""build_model.py - P38 SM_TeduhCapex: Direct Lake on OneLake over LH_TeduhCapex (no schemas), written as TMDL.
Shape from P37's delivered build_model.py (S273, S274). CRLF on every .tmdl. Measures follow the contracts in the
Design Package (guide tab 'Measures'); EAC and the flag come from Gold, not DAX. Writes model_dictionary.json for the
report's data dictionary (the Gold notebook loads it into the 'dictionary' table)."""
import json, os, sys, uuid
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "estate", "fabric")
WS = "aaaaaaaa-0000-4000-8000-000000000001"; LH = "aaaaaaaa-0000-4000-8000-000000000002"
M = os.path.join(OUT, "SM_TeduhCapex.SemanticModel")
NS = uuid.UUID("38a00000-0000-4000-8000-0000000000ff")
EXPR = "DirectLake - LH_TeduhCapex"
def tag(*k): return str(uuid.uuid5(NS, "/".join(k)))
S, I, D, DT, B = "string", "int64", "double", "dateTime", "boolean"
TABLES = {
    "AFE": ("dim_afe", "One row per original AFE (the family root): asset, type, status, requester, original tier.", [
        ("afe_no", S, 0), ("title", S, 0), ("asset_code", S, 1), ("afe_type", S, 0), ("status", S, 0), ("requester", S, 0), ("original_tier", S, 0),
        ("planned_start", DT, 0), ("planned_end", DT, 0), ("source", S, 1)]),
    "AFE status": ("gold_afe_status", "Gold status per AFE family: approved, actual, open commitment, EAC, headroom, supplement flag (contract C1-C9).", [
        ("root_afe_no", S, 1), ("asset_code", S, 1), ("afe_type", S, 1), ("status", S, 1), ("approved_rm", D, 1), ("actual_rm", D, 1), ("open_commit_rm", D, 1),
        ("committed_total_rm", D, 1), ("award_factor", D, 1), ("eac_rm", D, 1), ("eac_vs_approved", D, 1), ("headroom_rm", D, 1), ("supplement_needed", B, 0)]),
    "GL": ("fact_gl", "GL actuals by AFE, cost element and month (ERP extract).", [
        ("afe_no", S, 1), ("root_afe_no", S, 1), ("element_code", S, 1), ("po_no", S, 1), ("month_date", DT, 1), ("amount_rm", D, 1)]),
    "PO": ("fact_po", "Purchase orders with invoiced and open amounts.", [
        ("po_no", S, 0), ("afe_no", S, 1), ("root_afe_no", S, 1), ("element_code", S, 1), ("vendor", S, 0), ("awarded_on", DT, 0),
        ("po_value_rm", D, 1), ("invoiced_rm", D, 1), ("open_rm", D, 1)]),
    "Estimate": ("fact_estimate", "AFE estimate by cost element (original AFEs).", [("afe_no", S, 1), ("root_afe_no", S, 1), ("element_code", S, 1), ("estimate_rm", D, 1)]),
    "Phasing": ("fact_phasing", "Planned phasing by AFE and year, dated 1 January.", [("afe_no", S, 1), ("root_afe_no", S, 1), ("year", I, 1), ("year_date", DT, 1), ("planned_rm", D, 1)]),
    "Budget": ("fact_budget", "Capex budget (WP&B) by asset and year, dated 1 January.", [("asset_code", S, 1), ("year", I, 1), ("year_date", DT, 1), ("budget_rm", D, 1)]),
    "Decision": ("fact_decision", "One row per approval step of every request (originals and supplements).", [
        ("afe_no", S, 0), ("root_afe_no", S, 1), ("step", S, 0), ("role", S, 0), ("approver", S, 0), ("submitted_on", DT, 0), ("decided_on", DT, 0),
        ("decided_month", DT, 1), ("outcome", S, 0), ("comment", S, 0), ("days", I, 1), ("request_tier", S, 0), ("kind", S, 0), ("asset_code", S, 1)]),
    "Waiting": ("gold_waiting", "Requests waiting for a decision and how long.", [
        ("afe_no", S, 0), ("root_afe_no", S, 1), ("title", S, 0), ("kind", S, 0), ("asset_code", S, 1), ("amount_rm", D, 0), ("status", S, 0),
        ("with_role", S, 0), ("days_waiting", I, 0)]),
    "Date": ("dim_date", "Months from Jan 2024 to Dec 2028.", [("month_date", DT, 0), ("year", I, 0), ("month_no", I, 1), ("month_label", S, 0)]),
    "Asset": ("dim_asset", "Five assets.", [("asset_code", S, 0), ("asset_name", S, 0), ("asset_kind", S, 0), ("asset_manager", S, 0)]),
    "Cost element": ("dim_cost_element", "Seven cost elements.", [("element_code", S, 1), ("element_name", S, 0), ("procured_by_po", B, 1)]),
    "Tier": ("dim_tier", "LOA tiers.", [("tier", S, 0), ("approver_role", S, 0), ("sort", I, 1)]),
    "Dictionary": ("dictionary", "Every measure with its definition (data dictionary page).", [("measure", S, 0), ("folder", S, 0), ("definition", S, 0)]),
}
SORT = {("Date", "month_label"): "month_date", ("Tier", "approver_role"): "sort"}
FMT = {D: "#,0.00", DT: "dd mmm yyyy"}
RELS = [("AFE status", "root_afe_no", "AFE", "afe_no"), ("GL", "root_afe_no", "AFE", "afe_no"), ("GL", "month_date", "Date", "month_date"),
        ("GL", "element_code", "Cost element", "element_code"), ("PO", "root_afe_no", "AFE", "afe_no"), ("PO", "element_code", "Cost element", "element_code"),
        ("Estimate", "root_afe_no", "AFE", "afe_no"), ("Estimate", "element_code", "Cost element", "element_code"), ("Phasing", "root_afe_no", "AFE", "afe_no"),
        ("Phasing", "year_date", "Date", "month_date"), ("Budget", "asset_code", "Asset", "asset_code"), ("Budget", "year_date", "Date", "month_date"),
        ("Decision", "root_afe_no", "AFE", "afe_no"), ("Decision", "request_tier", "Tier", "tier"), ("Decision", "decided_month", "Date", "month_date"),
        ("Waiting", "root_afe_no", "AFE", "afe_no"), ("AFE", "asset_code", "Asset", "asset_code")]
RM = '"RM "#,0'   # millions come from visual display units (S183: Desktop ignores scaling commas)
def m(*lines): return "\n\t\t\t".join(lines)
OPEN = "'AFE status'[status] = \"Approved\""
MEAS = [
    ("AFE status", "Open approved", f"CALCULATE ( SUM ( 'AFE status'[approved_rm] ), {OPEN} )", RM, "Portfolio", "Approved amount (original plus approved supplements) of open AFEs, at the data cut; not sliced by Year."),
    ("AFE status", "Open committed", f"CALCULATE ( SUM ( 'AFE status'[committed_total_rm] ), {OPEN} )", RM, "Portfolio", "Lifetime actual plus open purchase orders of open AFEs."),
    ("AFE status", "Open EAC", f"CALCULATE ( SUM ( 'AFE status'[eac_rm] ), {OPEN} )", RM, "Portfolio", "Estimate at completion of open AFEs, computed in Gold (contract C7)."),
    ("AFE status", "Open headroom", f"CALCULATE ( SUM ( 'AFE status'[headroom_rm] ), {OPEN} )", RM, "Portfolio", "Approved minus actual minus open commitment, open AFEs."),
    ("AFE status", "Open AFEs", f"COALESCE ( CALCULATE ( COUNTROWS ( 'AFE status' ), {OPEN} ), 0 )", "#,0", "Portfolio", "Number of approved AFEs still spending."),
    ("AFE status", "EAC % of approval", "DIVIDE ( [Open EAC], [Open approved] )", "0%", "Portfolio", "Open EAC over open approved; blank when nothing is approved."),
    ("AFE status", "AFEs needing a supplement", "COALESCE ( CALCULATE ( COUNTROWS ( 'AFE status' ), 'AFE status'[supplement_needed] = TRUE () ), 0 )", "#,0", "Portfolio", "Open AFEs with EAC more than 110% of approval (contract C9)."),
    ("AFE status", "Over approval", "SUMX ( FILTER ( 'AFE status', 'AFE status'[supplement_needed] = TRUE () ), 'AFE status'[eac_rm] - 'AFE status'[approved_rm] )", RM, "Portfolio", "EAC minus approval, summed over flagged AFEs."),
    ("AFE status", "Approved", "SUM ( 'AFE status'[approved_rm] )", RM, "AFE", "Approved amount of the AFEs in context (detail page)."),
    ("AFE status", "Actual to date", "SUM ( 'AFE status'[actual_rm] )", RM, "AFE", "Lifetime actual of the AFEs in context."),
    ("AFE status", "Open commitment", "SUM ( 'AFE status'[open_commit_rm] )", RM, "AFE", "Open purchase-order value not yet invoiced."),
    ("AFE status", "Committed", "SUM ( 'AFE status'[committed_total_rm] )", RM, "AFE", "Actual plus open purchase orders."),
    ("AFE status", "EAC", "SUM ( 'AFE status'[eac_rm] )", RM, "AFE", "Estimate at completion of the AFEs in context."),
    ("AFE status", "Headroom", "SUM ( 'AFE status'[headroom_rm] )", RM, "AFE", "Approved minus committed."),
    ("AFE status", "EAC vs approval", "DIVIDE ( [EAC], [Approved] )", "0%", "AFE", "EAC over approved for the AFEs in context."),
    ("AFE status", "Trigger 110%", "IF ( NOT ISBLANK ( [Approved] ), 1.1 )", "0%", "AFE", "The supplement trigger line."),
    ("GL", "Actual", "SUM ( GL[amount_rm] )", RM, "Spend", "GL actual in the period in context (follows the Year slicer)."),
    ("GL", "Data cut", "CALCULATE ( MAX ( GL[month_date] ), REMOVEFILTERS () )", "mmm yyyy", "Spend", "Last month with GL actuals."),
    ("GL", "Cumulative actual", m("VAR mx = MAX ( 'Date'[month_date] )", "RETURN", "\tIF ( mx <= [Data cut], CALCULATE ( [Actual], DATESBETWEEN ( 'Date'[month_date], DATE ( YEAR ( mx ), 1, 1 ), mx ) ) )"),
     RM, "Spend", "Actual from January of the year in context to the month in context; blank after the data cut."),
    ("Budget", "Budget", "CALCULATE ( SUM ( Budget[budget_rm] ), REMOVEFILTERS ( 'Date'[month_date], 'Date'[month_label], 'Date'[month_no] ) )", RM, "Spend", "Capex budget (WP&B) of the year in context; the month filter is removed (S277: column-scoped)."),
    ("Budget", "Budget to date", "[Budget] * MAX ( 'Date'[month_no] ) / 12", RM, "Spend", "Straight-line budget to the month in context."),
    ("Budget", "Actual % of budget", "DIVIDE ( [Actual], [Budget] )", "0%", "Spend", "Actual in the period over the year's budget."),
    ("Estimate", "Estimate", "SUM ( Estimate[estimate_rm] )", RM, "AFE", "Original AFE estimate by cost element."),
    ("PO", "PO value", "SUM ( PO[po_value_rm] )", RM, "AFE", "Purchase-order value."),
    ("PO", "Invoiced", "SUM ( PO[invoiced_rm] )", RM, "AFE", "Invoiced against purchase orders."),
    ("PO", "POs", "COALESCE ( COUNTROWS ( PO ), 0 )", "#,0", "AFE", "Number of purchase orders."),
    ("Phasing", "Planned", "SUM ( Phasing[planned_rm] )", RM, "AFE", "Planned phasing by year."),
    ("Decision", "Requests", "COALESCE ( DISTINCTCOUNT ( Decision[afe_no] ), 0 )", "#,0", "Approvals", "Requests (originals and supplements) with a decision step."),
    ("Decision", "Finance days per request", "DIVIDE ( CALCULATE ( SUM ( Decision[days] ), Decision[step] = \"Finance check\" ), CALCULATE ( DISTINCTCOUNT ( Decision[afe_no] ), Decision[step] = \"Finance check\" ) )", "0.0", "Approvals", "Days in the finance check per request; a returned request counts its finance days twice."),
    ("Decision", "LOA days per request", "DIVIDE ( CALCULATE ( SUM ( Decision[days] ), Decision[step] = \"LOA approval\" ), CALCULATE ( DISTINCTCOUNT ( Decision[afe_no] ), Decision[step] = \"LOA approval\" ) )", "0.0", "Approvals", "Days at the LOA approver per request."),
    ("Decision", "Submit to decision", m("VAR r = FILTER ( VALUES ( Decision[afe_no] ), CALCULATE ( COUNTROWS ( Decision ), Decision[step] = \"LOA approval\" ) > 0 )", "RETURN",
     "\tAVERAGEX ( r, CALCULATE ( DATEDIFF ( MIN ( Decision[submitted_on] ), MAX ( Decision[decided_on] ), DAY ) ) )"), "0.0", "Approvals", "Mean days from first submit to the LOA decision, decided requests."),
    ("Decision", "Median submit to decision", m("VAR r = FILTER ( VALUES ( Decision[afe_no] ), CALCULATE ( COUNTROWS ( Decision ), Decision[step] = \"LOA approval\" ) > 0 )", "RETURN",
     "\tMEDIANX ( r, CALCULATE ( DATEDIFF ( MIN ( Decision[submitted_on] ), MAX ( Decision[decided_on] ), DAY ) ) )"), "0", "Approvals", "Median of the same."),
    ("Decision", "Returned", "COALESCE ( CALCULATE ( COUNTROWS ( Decision ), Decision[outcome] = \"Returned\" ), 0 )", "#,0", "Approvals", "Steps where finance returned the request."),
    ("Decision", "Rejected", "COALESCE ( CALCULATE ( COUNTROWS ( Decision ), Decision[outcome] = \"Rejected\" ), 0 )", "#,0", "Approvals", "Requests rejected at the LOA step."),
    ("Waiting", "Waiting for a decision", "COALESCE ( COUNTROWS ( Waiting ), 0 )", "#,0", "Approvals", "Requests in Submitted, Finance check or LOA approval now."),
    ("Waiting", "Days waiting", "MAX ( Waiting[days_waiting] )", "0", "Approvals", "Days since the request reached its current step."),
    ("AFE status", "Title scoreboard", m("VAR y = SELECTEDVALUE ( 'Date'[year], YEAR ( [Data cut] ) )", "VAR p = [Actual % of budget]", "RETURN",
     "\t\"Capex is at \" & FORMAT ( p, \"0%\" ) & \" of the \" & y & \" budget at \" & FORMAT ( [Data cut], \"mmm yyyy\" )"), None, "Titles", "Scoreboard title."),
    ("AFE status", "Subtitle scoreboard", "FORMAT ( [AFEs needing a supplement], \"0\" ) & \" open AFEs are heading more than 10% over approval, RM \" & FORMAT ( [Over approval] / 1000000, \"#,0.0\" ) & \"m above it\"", None, "Titles", "Scoreboard subtitle."),
    ("AFE status", "Title watchlist", "FORMAT ( [AFEs needing a supplement], \"0\" ) & \" AFEs need a supplementary AFE\"", None, "Titles", "Watchlist title."),
    ("Decision", "Title approvals", m("VAR t3 = CALCULATE ( [Submit to decision], Decision[request_tier] = \"T3\" )", "VAR t1 = CALCULATE ( [Submit to decision], Decision[request_tier] = \"T1\" )", "RETURN",
     "\t\"CEO-tier requests take \" & FORMAT ( t3, \"0.0\" ) & \" days from submit to decision, against \" & FORMAT ( t1, \"0.0\" ) & \" at T1\""), None, "Titles", "Approvals title."),
    ("AFE status", "Disclaimer", "\"Teduh Samudera Energy is fictional. All figures are synthetic. GL actuals to \" & FORMAT ( [Data cut], \"mmm yyyy\" ) & \". Amounts in RM; cards and charts in millions.\"", None, "Titles", "Footer text."),
    ("AFE", "Title detail", "IF ( HASONEVALUE ( AFE[afe_no] ), SELECTEDVALUE ( AFE[afe_no] ) & \": \" & SELECTEDVALUE ( AFE[title] ), \"Pick one AFE in the slicer\" )", None, "Titles", "AFE detail title."),
]
def tmdl_table(name, src, desc, cols):
    q = "'%s'" % name if " " in name else name
    L = ["/// " + desc, "table %s" % q, "\tlineageTag: %s" % tag(name), ""]
    for t, mname, dax, fmt, folder, mdesc in MEAS:
        if t != name: continue
        mq = "'%s'" % mname if any(c in mname for c in " -%") else mname
        L.append("\t/// " + mdesc)
        if "\n" in dax:
            L += ["\tmeasure %s =" % mq, "\t\t\t" + dax]
        else:
            L.append("\tmeasure %s = %s" % (mq, dax))
        if fmt:
            L.append("\t\tformatString: %s" % (('"' + fmt.replace('"', '""') + '"') if fmt.startswith('"') and fmt.endswith('"') else fmt))
        L += ["\t\tdisplayFolder: %s" % folder, "\t\tlineageTag: %s" % tag(name, "m", mname), ""]
    for c, typ, hidden in cols:
        L += ["\tcolumn %s" % c, "\t\tdataType: %s" % typ]
        if hidden: L.append("\t\tisHidden")
        if typ in FMT: L.append("\t\tformatString: %s" % FMT[typ])
        L += ["\t\tsummarizeBy: none", "\t\tsourceColumn: %s" % c]
        if (name, c) in SORT: L.append("\t\tsortByColumn: %s" % SORT[(name, c)])
        L += ["\t\tlineageTag: %s" % tag(name, c), ""]
    L += ["\tpartition %s = entity" % q, "\t\tmode: directLake", "\t\tsource", "\t\t\tentityName: %s" % src, "\t\t\texpressionSource: '%s'" % EXPR, ""]
    return "\n".join(L)
def crlf(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f: f.write(text.replace("\r\n", "\n").replace("\n", "\r\n"))
def build():
    d = os.path.join(M, "definition")
    crlf(os.path.join(d, "database.tmdl"), "database SM_TeduhCapex\n\tcompatibilityLevel: 1606\n\tcompatibilityMode: powerBI\n\tlanguage: 1033\n\n")
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3", "\tdiscourageImplicitMeasures", "\tsourceQueryCulture: en-US",
             "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "", "annotation __PBI_ServiceStoredInTmdl = reserved", ""] + \
            ["ref table %s" % ("'%s'" % t if " " in t else t) for t in TABLES] + [""]
    crlf(os.path.join(d, "model.tmdl"), "\n".join(model))
    crlf(os.path.join(d, "expressions.tmdl"), "/// Direct Lake binding to LH_TeduhCapex via OneLake (Lakehouse without schemas; shape from P37).\n"
         "expression '%s' =\n\t\tlet\n\t\t    Source = AzureStorage.DataLake(\"https://onelake.dfs.fabric.microsoft.com/%s/%s\", [HierarchicalNavigation=true])\n\t\tin\n\t\t    Source\n\n" % (EXPR, WS, LH))
    for name, (src, desc, cols) in TABLES.items():
        crlf(os.path.join(d, "tables", name + ".tmdl"), tmdl_table(name, src, desc, cols))
    rel = []
    for a, ac, b, bc in RELS:
        qa = "'%s'" % a if " " in a else a; qb = "'%s'" % b if " " in b else b
        rel += ["relationship %s" % tag("rel", a, ac), "\tfromColumn: %s.%s" % (qa, ac), "\ttoColumn: %s.%s" % (qb, bc), ""]
    crlf(os.path.join(d, "relationships.tmdl"), "\n".join(rel))
    with open(os.path.join(M, "definition.pbism"), "w", encoding="utf-8", newline="\n") as f:
        f.write('{\n  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",\n  "version": "4.2",\n  "settings": {}\n}\n')
    with open(os.path.join(M, ".platform"), "w", encoding="utf-8", newline="\n") as f:
        f.write('{\n  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",\n'
                '  "metadata": {"type": "SemanticModel", "displayName": "SM_TeduhCapex", "description": "P38 Direct Lake model: capex budget, AFEs, commitments, actuals, EAC, approvals."},\n'
                '  "config": {"version": "2.0", "logicalId": "38a00000-0000-4000-8000-000000000006"}\n}\n')
    json.dump([dict(measure=n, folder=f, definition=ds) for t, n, dax, fmt, f, ds in MEAS if f != "Titles"],
              open(os.path.join(HERE, "nb", "model_dictionary.json"), "w"), indent=1)
if __name__ == "__main__":
    build(); print("tables", len(TABLES), "relationships", len(RELS), "measures", len(MEAS))
