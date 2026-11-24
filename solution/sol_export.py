# sol_export.py - P38: put both apps into solution TeduhCapex, list its components, export it (unmanaged), save the zip.
# Runs on Windows from the P38 runner. Uses dv_build.call (az token, never printed). Prints one JSON line.
import base64, json, os, sys
sys.stdout.reconfigure(encoding="ascii", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "02_Build", "app_data"))
from dv_build import call, ok
SOL = "TeduhCapex"
APPS = {"Teduh Capex": "canvas f8455d3f", "P38 AFE Spend": "code app d4b5606b"}   # canvasapps.name is a logical name, not the app id: match displayname
log = []
try:
    for name, label in APPS.items():
        s, j, _ = call("GET", ("/canvasapps?$select=canvasappid,name,displayname&$filter=displayname eq '%s'" % name).replace(" ", "%20"), sol=False)
        if not (ok(s) and j["value"]):
            raise RuntimeError("canvasapp row not found for %s: %s %s" % (label, s, str(j)[:300]))
        if len(j["value"]) != 1: raise RuntimeError("%d canvasapp rows named %s" % (len(j["value"]), name))
        cid = j["value"][0]["canvasappid"]; log.append("%s -> %s" % (name, j["value"][0]["name"]))
        s, j, _ = call("POST", "/AddSolutionComponent", {"ComponentId": cid, "ComponentType": 300, "SolutionUniqueName": SOL,
                                                       "AddRequiredComponents": False, "DoNotIncludeSubcomponents": False}, sol=False)
        if not ok(s): raise RuntimeError("add %s %s %s" % (label, s, str(j)[:500]))
        log.append("added %s (%s)" % (label, cid))
    s, j, _ = call("GET", ("/solutions?$select=solutionid,version&$filter=uniquename eq '%s'" % SOL).replace(" ", "%20"), sol=False)
    sid, ver = j["value"][0]["solutionid"], j["value"][0]["version"]
    s, j, _ = call("GET", "/solutioncomponents?$select=componenttype,objectid&$filter=_solutionid_value%%20eq%%20%s&$top=500" % sid, sol=False)
    kinds = {}
    for c in j.get("value", []): kinds[c["componenttype"]] = kinds.get(c["componenttype"], 0) + 1
    log.append("components by type %s" % kinds)
    s, j, _ = call("POST", "/ExportSolution", {"SolutionName": SOL, "Managed": False}, sol=False)
    if not ok(s): raise RuntimeError("export %s %s" % (s, str(j)[:800]))
    data = base64.b64decode(j["ExportSolutionFile"])
    out = os.path.join(HERE, "%s_%s.zip" % (SOL, ver.replace(".", "_")))
    open(out, "wb").write(data)
    print(json.dumps({"ok": True, "log": log, "zip": os.path.basename(out), "bytes": len(data), "version": ver, "component_types": kinds}))
except Exception as e:
    print(json.dumps({"ok": False, "log": log, "error": str(e)[:1500]})); sys.exit(1)
