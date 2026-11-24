# flow_deploy.py - P38: connection references + the 'P38 AFE approval' workflow row (from clientdata.json) + activation.
# Runs on Windows from the P38 runner. Idempotent: updates clientdata when the flow exists. Prints one JSON line.
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app_data"))
from dv_build import call, ok
CONNS = {"tsc_commondataserviceforapps": ("shared_commondataserviceforapps", "<dataverse-connection-id>", "P38 Dataverse"),
         "tsc_approvals": ("shared_approvals", "<approvals-connection-id>", "P38 Approvals"),
         "tsc_office365": ("shared_office365", "<office365-connection-id>", "P38 Office 365 Outlook")}
NAME = "P38 AFE approval"
log = []
try:
    for ln, (api, cid, disp) in CONNS.items():
        s, j, _ = call("GET", ("/connectionreferences?$select=connectionreferenceid&$filter=connectionreferencelogicalname eq '%s'" % ln).replace(" ", "%20"), sol=False)
        if ok(s) and j["value"]:
            log.append("ref %s exists" % ln); continue
        s, j, _ = call("POST", "/connectionreferences", {"connectionreferencelogicalname": ln, "connectionreferencedisplayname": disp,
                       "connectorid": "/providers/Microsoft.PowerApps/apis/" + api, "connectionid": cid})
        if not ok(s): raise RuntimeError("ref %s %s %s" % (ln, s, j))
        log.append("ref %s created" % ln)
    cd = json.dumps(json.load(open(os.path.join(HERE, "clientdata.json"))))
    s, j, _ = call("GET", ("/workflows?$select=workflowid,statecode&$filter=name eq '%s' and category eq 5" % NAME).replace(" ", "%20"), sol=False)
    if ok(s) and j["value"]:
        wid = j["value"][0]["workflowid"]
        if j["value"][0]["statecode"] == 1:
            s, j2, _ = call("PATCH", "/workflows(%s)" % wid, {"statecode": 0, "statuscode": 1}, sol=False); log.append("deactivate %s" % s)
        s, j2, _ = call("PATCH", "/workflows(%s)" % wid, {"clientdata": cd}, sol=False)
        if not ok(s): raise RuntimeError("update %s %s" % (s, j2))
        log.append("flow updated")
    else:
        s, j, h = call("POST", "/workflows", {"category": 5, "type": 1, "name": NAME, "primaryentity": "none", "clientdata": cd,
                                              "description": "P38 capex AFE desk: finance check, LOA approval, write back, email. Fictional company."})
        if not ok(s): raise RuntimeError("create %s %s" % (s, j))
        wid = h.get("OData-EntityId", "").split("(")[-1].rstrip(")"); log.append("flow created")
    s, j, _ = call("PATCH", "/workflows(%s)" % wid, {"statecode": 1, "statuscode": 2}, sol=False)
    if not ok(s): raise RuntimeError("activate %s %s" % (s, j))
    s, j, _ = call("GET", "/workflows(%s)?$select=statecode,statuscode,name,resourceid" % wid, sol=False)
    print(json.dumps({"ok": True, "log": log, "workflowid": wid, "state": j}))
except Exception as e:
    print(json.dumps({"ok": False, "log": log, "error": str(e)[:1500]})); sys.exit(1)
