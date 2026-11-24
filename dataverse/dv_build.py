# dv_build.py - P38: Dataverse publisher, solution, 8 tables and the seed rows in "US Environment" (<yourorg>).
# Runs on Windows from the P38 runner (task type py). Idempotent: skips what exists. Token from az (never printed).
# Usage: dv_build.py [schema|seed|verify|all]. Prints one JSON summary line; exit 1 on any failure.
import csv, json, os, subprocess, sys, time, urllib.request, urllib.error, uuid
ORG = "https://<yourorg>.crm.dynamics.com"; API = ORG + "/api/data/v9.2"
SOL, PFX = "TeduhCapex", "tsc"
OWNER = "you@example.com"
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "..", "data", "out")
_t = {"v": None, "exp": 0}
def token():
    if _t["v"] and _t["exp"] - time.time() > 300: return _t["v"]
    az = "az.cmd" if os.name == "nt" else "az"
    p = subprocess.run([az, "account", "get-access-token", "--resource", ORG, "-o", "json"], capture_output=True, text=True, timeout=90)
    j = json.loads(p.stdout or "{}")
    if not j.get("accessToken"): raise RuntimeError("NO_TOKEN " + p.stderr[:300])
    _t.update(v=j["accessToken"], exp=float(j.get("expires_on") or time.time() + 900)); return _t["v"]
def call(method, path, body=None, sol=True):
    url = path if path.startswith("http") else API + path
    data = None if body is None else json.dumps(body).encode("utf-8")
    for attempt in range(5):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "Bearer " + token()); req.add_header("OData-Version", "4.0"); req.add_header("Accept", "application/json")
        if data is not None: req.add_header("Content-Type", "application/json; charset=utf-8")
        if sol: req.add_header("MSCRM.SolutionUniqueName", SOL)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                t = r.read().decode("utf-8", "replace"); return r.status, (json.loads(t) if t else None), dict(r.headers)
        except urllib.error.HTTPError as e:
            t = e.read().decode("utf-8", "replace")
            if e.code in (429, 503) or "concurrent" in t.lower() or "locked" in t.lower():
                time.sleep(5 * (attempt + 1)); continue
            return e.code, t[:1500], dict(e.headers)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:   # transient network (WinError 10060, first run 24 Nov)
            time.sleep(10 * (attempt + 1)); continue
    return 599, "retries exhausted", {}
def lab(s): return {"@odata.type": "Microsoft.Dynamics.CRM.Label", "LocalizedLabels": [{"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": s, "LanguageCode": 1033}]}
def attr(kind, name, disp, **k):
    a = {"SchemaName": name, "DisplayName": lab(disp), "RequiredLevel": {"Value": "None"}}
    if kind == "text": a.update({"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata", "MaxLength": k.get("n", 200), "FormatName": {"Value": "Text"}})
    elif kind == "memo": a.update({"@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata", "MaxLength": 4000, "Format": "TextArea"})
    elif kind == "dec": a.update({"@odata.type": "Microsoft.Dynamics.CRM.DecimalAttributeMetadata", "Precision": k.get("p", 2), "MinValue": -100000000000, "MaxValue": 100000000000})
    elif kind == "int": a.update({"@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata", "Format": "None", "MinValue": 0, "MaxValue": 2100000000})
    elif kind == "date": a.update({"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata", "Format": "DateOnly", "DateTimeBehavior": {"Value": "DateOnly"}})
    elif kind == "datetime": a.update({"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata", "Format": "DateAndTime", "DateTimeBehavior": {"Value": "UserLocal"}})
    elif kind == "bool": a.update({"@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata", "DefaultValue": False,
                                   "OptionSet": {"TrueOption": {"Value": 1, "Label": lab("Yes")}, "FalseOption": {"Value": 0, "Label": lab("No")}}})
    return a
T = {  # table: (display, plural, primary (schema, display), [attributes])
 "tsc_afe": ("AFE", "AFEs", ("tsc_afeno", "AFE no"), [("text", "tsc_title", "Title", {"n": 300}), ("text", "tsc_assetcode", "Asset code", {"n": 10}),
   ("text", "tsc_afetype", "AFE type", {"n": 40}), ("text", "tsc_kind", "Kind", {"n": 20}), ("text", "tsc_parentafeno", "Parent AFE no", {"n": 30}),
   ("dec", "tsc_amount", "Amount (RM)", {}), ("text", "tsc_status", "Status", {"n": 30}), ("text", "tsc_loatier", "LOA tier", {"n": 5}),
   ("text", "tsc_requestername", "Requester", {"n": 100}), ("text", "tsc_requesteremail", "Requester email", {"n": 200}),
   ("memo", "tsc_justification", "Justification", {}), ("date", "tsc_plannedstart", "Planned start", {}), ("date", "tsc_plannedend", "Planned end", {}),
   ("date", "tsc_raisedon", "Raised on", {}), ("date", "tsc_submittedon", "Submitted on", {}), ("date", "tsc_decidedon", "Decided on", {}),
   ("text", "tsc_source", "Source", {"n": 10}), ("memo", "tsc_lastcomment", "Last comment", {})]),
 "tsc_afeline": ("AFE line", "AFE lines", ("tsc_name", "Line"), [("text", "tsc_afeno", "AFE no", {"n": 30}), ("text", "tsc_elementcode", "Element code", {"n": 10}), ("dec", "tsc_estimate", "Estimate (RM)", {})]),
 "tsc_afephasing": ("AFE phasing", "AFE phasing", ("tsc_name", "Phasing"), [("text", "tsc_afeno", "AFE no", {"n": 30}), ("int", "tsc_year", "Year", {}), ("dec", "tsc_planned", "Planned (RM)", {})]),
 "tsc_afedecision": ("AFE decision", "AFE decisions", ("tsc_name", "Decision"), [("text", "tsc_afeno", "AFE no", {"n": 30}), ("text", "tsc_step", "Step", {"n": 30}),
   ("text", "tsc_role", "Role", {"n": 40}), ("text", "tsc_approvername", "Approver", {"n": 100}), ("text", "tsc_approveremail", "Approver email", {"n": 200}),
   ("date", "tsc_submittedon", "Submitted on", {}), ("date", "tsc_decidedon", "Decided on", {}), ("text", "tsc_outcome", "Outcome", {"n": 20}), ("memo", "tsc_comment", "Comment", {})]),
 "tsc_loatier": ("LOA tier", "LOA tiers", ("tsc_tiercode", "Tier"), [("text", "tsc_approverrole", "Approver role", {"n": 60}), ("dec", "tsc_lower", "Lower (RM)", {}),
   ("dec", "tsc_upper", "Upper (RM)", {}), ("text", "tsc_approveremail", "Approver email", {"n": 200}), ("int", "tsc_steporder", "Step order", {})]),
 "tsc_asset": ("Asset", "Assets", ("tsc_assetcode", "Asset code"), [("text", "tsc_assetname", "Asset name", {"n": 100}), ("text", "tsc_assetkind", "Asset kind", {"n": 40}), ("text", "tsc_assetmanager", "Asset manager", {"n": 100}), ("text", "tsc_manageremail", "Manager email", {"n": 200})]),
 "tsc_assetbudget": ("Asset budget", "Asset budgets", ("tsc_name", "Asset and year"), [("text", "tsc_assetcode", "Asset code", {"n": 10}), ("int", "tsc_year", "Year", {}),
   ("dec", "tsc_budget", "Budget (RM)", {}), ("dec", "tsc_actual", "Actual (RM)", {}), ("dec", "tsc_approvedinyear", "Approved in year (RM)", {}), ("dec", "tsc_left", "Budget left (RM)", {}),
   ("datetime", "tsc_refreshedon", "Refreshed on", {})]),
 "tsc_afestatus": ("AFE status", "AFE statuses", ("tsc_afeno", "AFE no"), [("dec", "tsc_approved", "Approved (RM)", {}), ("dec", "tsc_actual", "Actual (RM)", {}),
   ("dec", "tsc_opencommit", "Open commitment (RM)", {}), ("dec", "tsc_committed", "Committed (RM)", {}), ("dec", "tsc_eac", "EAC (RM)", {}), ("dec", "tsc_eacpct", "EAC % of approval", {"p": 4}),
   ("dec", "tsc_headroom", "Headroom (RM)", {}), ("bool", "tsc_supplementneeded", "Supplement needed", {}), ("text", "tsc_assetcode", "Asset code", {"n": 10}),
   ("text", "tsc_status", "AFE status", {"n": 30}), ("datetime", "tsc_refreshedon", "Refreshed on", {})]),
}
LOG = []
def ok(s): return s in (200, 201, 204)
def schema():
    s, j, _ = call("GET", "/publishers?$select=publisherid&$filter=uniquename eq 'TeduhCapex'".replace(" ", "%20"), sol=False)
    if ok(s) and j["value"]: pub = j["value"][0]["publisherid"]
    else:
        s, j, h = call("POST", "/publishers", {"uniquename": "TeduhCapex", "friendlyname": "Teduh Capex (fictional)", "customizationprefix": PFX, "customizationoptionvalueprefix": 10038}, sol=False)
        if not ok(s): raise RuntimeError("publisher %s %s" % (s, j))
        pub = h.get("OData-EntityId", "").split("(")[-1].rstrip(")")
    s, j, _ = call("GET", "/solutions?$select=solutionid&$filter=uniquename eq 'TeduhCapex'".replace(" ", "%20"), sol=False)
    if not (ok(s) and j["value"]):
        s, j, _ = call("POST", "/solutions", {"uniquename": SOL, "friendlyname": "Teduh Capex AFE Desk", "version": "1.0.0.0", "publisherid@odata.bind": "/publishers(%s)" % pub}, sol=False)
        if not ok(s): raise RuntimeError("solution %s %s" % (s, j))
    LOG.append("publisher+solution ok")
    for t, (disp, plural, (pn, pdisp), attrs) in T.items():
        s, j, _ = call("GET", "/EntityDefinitions(LogicalName='%s')?$select=LogicalName,EntitySetName" % t, sol=False)
        if not ok(s):
            prim = attr("text", pn, pdisp, n=100); prim["IsPrimaryName"] = True; prim["RequiredLevel"] = {"Value": "ApplicationRequired"}
            body = {"@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata", "SchemaName": t, "DisplayName": lab(disp), "DisplayCollectionName": lab(plural),
                    "Description": lab("P38 Capex AFE desk (fictional, synthetic data)"), "OwnershipType": "UserOwned", "IsActivity": False,
                    "HasActivities": False, "HasNotes": False, "PrimaryNameAttribute": pn, "Attributes": [prim]}
            s, j, _ = call("POST", "/EntityDefinitions", body)
            if not ok(s): raise RuntimeError("table %s %s %s" % (t, s, j))
            LOG.append("table %s created" % t)
        for kind, an, ad, k in attrs:
            s, j, _ = call("GET", "/EntityDefinitions(LogicalName='%s')/Attributes(LogicalName='%s')?$select=LogicalName" % (t, an), sol=False)
            if ok(s): continue
            s, j, _ = call("POST", "/EntityDefinitions(LogicalName='%s')/Attributes" % t, attr(kind, an, ad, **k))
            if not ok(s): raise RuntimeError("attr %s.%s %s %s" % (t, an, s, j))
        LOG.append("table %s attrs ok" % t)
    s, j, _ = call("POST", "/PublishAllXml", {}, sol=False); LOG.append("publish %s" % s)
def esets():
    out = {}
    for t in T:
        s, j, _ = call("GET", "/EntityDefinitions(LogicalName='%s')?$select=EntitySetName" % t, sol=False); out[t] = j["EntitySetName"]
    return out
def rows(name): return list(csv.DictReader(open(os.path.join(DATA, name), encoding="utf-8")))
MY = "Siti Aisyah Kamal"   # the owner plays this requester in testing; other seeded requesters get fictional addresses
def seed():
    es = esets(); n = {}
    PEND = {}
    def ins(t, rec, key):   # queue; flushed per table by $batch (fast mode, 24 Nov: per-row GET+POST took 50+ min)
        PEND.setdefault(t, (key, []))[1].append(rec)
    for r in rows("dim_asset.csv"): ins("tsc_asset", {"tsc_assetcode": r["asset_code"], "tsc_assetname": r["asset_name"], "tsc_assetkind": r["asset_kind"], "tsc_assetmanager": r["asset_manager"], "tsc_manageremail": OWNER}, "tsc_assetcode")
    ins("tsc_loatier", {"tsc_tiercode": "FIN", "tsc_approverrole": "Finance controller", "tsc_lower": 0, "tsc_upper": None, "tsc_approveremail": OWNER, "tsc_steporder": 1}, "tsc_tiercode")
    for r in rows("loa_tier.csv"):
        ins("tsc_loatier", {"tsc_tiercode": r["tier_code"], "tsc_approverrole": r["approver_role"], "tsc_lower": float(r["lower_rm"]),
                            "tsc_upper": float(r["upper_rm"]) if r["upper_rm"] else None, "tsc_approveremail": OWNER, "tsc_steporder": 2}, "tsc_tiercode")
    em = lambda name: OWNER if name == MY else name.lower().replace(" ", ".") + "@teduhsamudera.example"
    for r in rows("afe.csv"):
        ins("tsc_afe", {"tsc_afeno": r["afe_no"], "tsc_title": r["title"], "tsc_assetcode": r["asset_code"], "tsc_afetype": r["afe_type"], "tsc_kind": r["kind"],
                        "tsc_parentafeno": r["parent_afe_no"] or None, "tsc_amount": float(r["amount_rm"]), "tsc_status": r["status"], "tsc_loatier": r["loa_tier"],
                        "tsc_requestername": r["requester"], "tsc_requesteremail": em(r["requester"]), "tsc_plannedstart": r["planned_start"], "tsc_plannedend": r["planned_end"],
                        "tsc_raisedon": r["raised_on"], "tsc_submittedon": r["submitted_on"], "tsc_decidedon": r["decided_on"], "tsc_source": "Seed"}, "tsc_afeno")
    for r in rows("afe_line.csv"):
        ins("tsc_afeline", {"tsc_name": r["afe_no"] + " " + r["element_code"], "tsc_afeno": r["afe_no"], "tsc_elementcode": r["element_code"], "tsc_estimate": float(r["estimate_rm"])}, "tsc_name")
    for r in rows("afe_phasing.csv"):
        ins("tsc_afephasing", {"tsc_name": r["afe_no"] + " " + r["year"], "tsc_afeno": r["afe_no"], "tsc_year": int(r["year"]), "tsc_planned": float(r["planned_rm"])}, "tsc_name")
    for i, r in enumerate(rows("afe_decision.csv")):
        ins("tsc_afedecision", {"tsc_name": "%s %s %s" % (r["afe_no"], r["step"], i), "tsc_afeno": r["afe_no"], "tsc_step": r["step"], "tsc_role": r["role"],
                                "tsc_approvername": r["approver"], "tsc_approveremail": OWNER, "tsc_submittedon": r["submitted_on"], "tsc_decidedon": r["decided_on"],
                                "tsc_outcome": r["outcome"], "tsc_comment": r["comment"]}, "tsc_name")
    for t, (key, recs) in PEND.items():
        have, url = set(), "/%s?$select=%s" % (es[t], key)
        while url:
            s_, j, _ = call("GET", url, sol=False)
            if not ok(s_): raise RuntimeError("read keys %s %s %s" % (t, s_, j))
            have |= {v[key] for v in j["value"]}; url = j.get("@odata.nextLink")
        todo = [r for r in recs if r[key] not in have]
        for i in range(0, len(todo), 100):
            batch_post(es[t], todo[i:i + 100])
        n[t] = len(todo); LOG.append("%s: %d existed, %d inserted" % (t, len(recs) - len(todo), len(todo)))
    LOG.append("seed inserted %s" % n)
def batch_post(eset, recs):
    b = "batch_p38_" + uuid.uuid4().hex[:12]
    parts = []
    for k, r in enumerate(recs, 1):
        parts.append("--%s\r\nContent-Type: application/http\r\nContent-Transfer-Encoding: binary\r\nContent-ID: %d\r\n\r\n"
                     "POST %s/%s HTTP/1.1\r\nContent-Type: application/json; type=entry\r\n\r\n%s\r\n" % (b, k, API, eset, json.dumps(r)))
    body = ("".join(parts) + "--%s--\r\n" % b).encode("utf-8")
    for attempt in range(5):
        req = urllib.request.Request(API + "/$batch", data=body, method="POST")
        req.add_header("Authorization", "Bearer " + token()); req.add_header("OData-Version", "4.0"); req.add_header("Accept", "application/json")
        req.add_header("Content-Type", "multipart/mixed; boundary=" + b); req.add_header("Prefer", "odata.continue-on-error")
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                t = r.read().decode("utf-8", "replace")
            bad = [ln for ln in t.splitlines() if ln.startswith("HTTP/1.1 ") and not ln.startswith(("HTTP/1.1 20",))]
            if bad: raise RuntimeError("batch %s: %d failed, first %s | %s" % (eset, len(bad), bad[0], t[:800]))
            return
        except urllib.error.HTTPError as e:
            t = e.read().decode("utf-8", "replace")
            if e.code in (429, 503): time.sleep(10 * (attempt + 1)); continue
            raise RuntimeError("batch %s HTTP %s %s" % (eset, e.code, t[:800]))
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(10 * (attempt + 1)); continue
    raise RuntimeError("batch %s retries exhausted" % eset)
def verify():
    es = esets(); c = {}
    for t in T:
        s, j, _ = call("GET", "/%s?$select=%s&$count=true&$top=1" % (es[t], T[t][2][0]), sol=False)
        c[t] = j.get("@odata.count") if ok(s) else "ERR %s" % s
    LOG.append("counts %s" % c); return c
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    try:
        if mode in ("schema", "all"): schema()
        if mode in ("seed", "all"): seed()
        c = verify(); print(json.dumps({"ok": True, "log": LOG, "counts": c}))
    except Exception as e:
        print(json.dumps({"ok": False, "log": LOG, "error": str(e)[:1500]})); sys.exit(1)
