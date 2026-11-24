"""build_estate.py - P38: the Fabric estate as Git item folders into <out>/fabric/ for deploy_items.py (fabric-cicd).
Items: LH_TeduhCapex (already created; folder kept for the repo), NB_TeduhCapex_ERP, NB_TeduhCapex_Gold,
NB_TeduhCapex_RunCopyJob (P34 shape, S178), PL_TeduhCapex_Nightly (verdict gate after every notebook, S179).
Notebook format from P37's build_notebooks.py (deployed, S274); RunCopyJob from P34's NB_RimbunCredit_RunCopyJob.
"""
import hashlib, json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "estate")
F = os.path.join(OUT, "fabric")
WS = "aaaaaaaa-0000-4000-8000-000000000001"; LH = "aaaaaaaa-0000-4000-8000-000000000002"
LID = {"LH_TeduhCapex": "38a00000-0000-4000-8000-000000000001", "NB_TeduhCapex_ERP": "38a00000-0000-4000-8000-0000000000a1",
       "NB_TeduhCapex_Gold": "38a00000-0000-4000-8000-0000000000a2", "NB_TeduhCapex_RunCopyJob": "38a00000-0000-4000-8000-0000000000a3",
       "PL_TeduhCapex_Nightly": "38a00000-0000-4000-8000-000000000005"}
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
HEAD = '''# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "%s",
# META       "default_lakehouse_name": "LH_TeduhCapex",
# META       "default_lakehouse_workspace_id": "%s",
# META       "known_lakehouses": [
# META         {
# META           "id": "%s"
# META         }
# META       ]
# META     }
# META   }
# META }
''' % (LH, WS, LH)
CELL_META = '''
# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
'''
def cell(src): return "\n# CELL ********************\n\n" + src.rstrip("\n") + "\n" + CELL_META
def pcell(src): return "\n# PARAMETERS CELL ********************\n\n" + src.rstrip("\n") + "\n" + CELL_META
def md(src): return "\n# MARKDOWN ********************\n\n" + "\n".join("# " + l if l else "#" for l in src.split("\n")) + "\n"
def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True); open(path, "w", encoding="utf-8", newline="\n").write(text)
def platform(folder, typ, name, desc):
    w(os.path.join(folder, ".platform"), json.dumps({"$schema": SCHEMA, "metadata": {"type": typ, "displayName": name, "description": desc},
                                                       "config": {"version": "2.0", "logicalId": LID[name]}}, indent=2) + "\n")

HELPER = '''
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
'''

def erp_nb(gen_src, ct):
    src = '__file__ = "/tmp/gen_teduh_capex.py"\n' + gen_src.split('if __name__ == "__main__":')[0]
    keys = ["afe_rows", "afe_line_rows", "decision_rows", "po_rows", "po_value_rm", "gl_rows", "gl_amount_rm", "budget_rows", "budget_rm"]
    exp = {k: ct[k] for k in keys}
    drv = HELPER + '''
EXPECTED = %s
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
''' % json.dumps(exp)
    return HEAD + md("NB_TeduhCapex_ERP (P38)\n\nThe ERP side of the sample: the same seeded generator writes POs, GL actuals, capex budget and cost elements to Bronze. Exits with a verdict JSON.") + cell(src) + cell(drv)

def gold_nb(mod_src, frozen_csv, dict_json):
    drv = HELPER + '''
import io
FROZEN = pd.read_csv(io.StringIO("""%s"""))
DICT = json.loads(r"""%s""")
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
''' % (frozen_csv.strip(), dict_json)
    return HEAD + md("NB_TeduhCapex_Gold (P38)\n\nSilver and Gold from Bronze; EAC contract C1-C9; outbound tables for CJ_Status_Out. Seed families must equal the frozen oracle to the cent. Exits with a verdict JSON.") + cell(mod_src) + cell(drv)

RUNCJ = '''# P38: run one Copy job on demand (Fabric job API, jobType=Execute) and wait (P34 shape, S178).
import json, time
import sempy.fabric as fabric
if not copy_job:
    raise ValueError("parameter copy_job is empty")
ws = fabric.get_workspace_id()
cj = fabric.resolve_item_id(copy_job, type="CopyJob", workspace=ws)
api = fabric.FabricRestClient()
r = api.post(f"v1/workspaces/{ws}/items/{cj}/jobs/instances?jobType=Execute")
print(f"[copyjob] {copy_job} id={cj} submit HTTP {r.status_code}")
if r.status_code != 202:
    raise RuntimeError(f"copy job submit failed HTTP {r.status_code}: {r.text[:500]}")
path = r.headers["Location"].split("api.fabric.microsoft.com/", 1)[-1]
status, polls, inst = "NotStarted", 0, {}
for polls in range(1, 121):
    time.sleep(10)
    inst = api.get(path).json(); status = inst.get("status", "Unknown")
    if status in ("Completed", "Failed", "Cancelled", "Deduped"):
        break
if status != "Completed":
    raise RuntimeError(f"copy job {copy_job} ended {status}: {json.dumps(inst.get('failureReason'))[:800]}")
notebookutils.notebook.exit(json.dumps({"verdict": "COPYJOB_OK", "copy_job": copy_job, "status": status, "polls": polls,
                                        "start": inst.get("startTimeUtc"), "end": inst.get("endTimeUtc")}))
'''

POL = {"timeout": "0.02:00:00", "retry": 0, "retryIntervalInSeconds": 30, "secureOutput": False, "secureInput": False}
def dep(n): return [{"activity": n, "dependencyConditions": ["Succeeded"]}] if n else []
def nb_act(name, nb, after, params=None):
    a = {"name": name, "type": "TridentNotebook", "dependsOn": dep(after), "policy": POL,
         "typeProperties": {"notebookId": LID[nb], "workspaceId": "00000000-0000-0000-0000-000000000000"}}
    if params: a["typeProperties"]["parameters"] = {k: {"value": v, "type": "string"} for k, v in params.items()}
    return a
def gate(step, run):
    ev = f"activity('{run}').output.result.exitValue"
    return {"name": f"Gate{step}", "type": "IfCondition", "dependsOn": dep(run), "typeProperties": {
        "expression": {"type": "Expression", "value": f"@and(not(equals(pipeline().parameters.p_block_at, '{step}')), endswith(string(json({ev}).verdict), '_OK'))"},
        "ifTrueActivities": [], "ifFalseActivities": [{"name": f"Fail{step}", "type": "Fail", "dependsOn": [], "typeProperties": {
            "message": {"type": "Expression", "value": f"@concat('{step} blocked: ', substring(string({ev}), 0, min(400, length(string({ev})))))"},
            "errorCode": f"P38_{step.upper()}_BLOCKED"}}]}}

def build():
    # no rmtree: the mount cannot delete; every file below is overwritten
    lh = os.path.join(F, "LH_TeduhCapex.Lakehouse"); w(os.path.join(lh, "lakehouse.metadata.json"), "{}\n")
    platform(lh, "Lakehouse", "LH_TeduhCapex", "P38 capex AFE desk: Bronze (Dataverse copy, ERP extract), Silver, Gold. Fictional, synthetic data.")
    data = os.path.join(HERE, "..", "data")
    gen = open(os.path.join(data, "gen_teduh_capex.py"), encoding="utf-8").read()
    ct = json.load(open(os.path.join(data, "out", "control_totals.json")))
    nbs = {"NB_TeduhCapex_ERP": (erp_nb(gen, ct), "P38 ERP extract: POs, GL actuals, capex budget to Bronze from the seeded generator; verdict ERP_OK."),
           "NB_TeduhCapex_Gold": (gold_nb(open(os.path.join(HERE, "nb", "gold_module.py"), encoding="utf-8").read(), open(os.path.join(HERE, "nb", "afe_status_oracle.csv")).read(), open(os.path.join(HERE, "nb", "model_dictionary.json")).read()),
                                  "P38 Silver and Gold: EAC contract, supplement flag, outbound tables; seed families equal the oracle; verdict GOLD_OK."),
           "NB_TeduhCapex_RunCopyJob": (HEAD + md("NB_TeduhCapex_RunCopyJob (P38)\n\nRuns one Copy job by name and waits (the pipeline Copy job activity needs a portal connection, S178).") + pcell('copy_job = ""') + cell(RUNCJ),
                                        "P38: runs one Copy job by name and waits; used by the nightly pipeline.")}
    res = []
    for n, (body, desc) in nbs.items():
        d = os.path.join(F, n + ".Notebook"); w(os.path.join(d, "notebook-content.py"), body); platform(d, "Notebook", n, desc)
        res.append((n, len(body), hashlib.sha256(body.encode()).hexdigest()[:12]))
    acts = [nb_act("RunCopyIn", "NB_TeduhCapex_RunCopyJob", None, {"copy_job": "CJ_AFE_In"}), gate("CopyIn", "RunCopyIn"),
            nb_act("RunERP", "NB_TeduhCapex_ERP", "GateCopyIn"), gate("ERP", "RunERP"),
            nb_act("RunGold", "NB_TeduhCapex_Gold", "GateERP"), gate("Gold", "RunGold"),
            nb_act("RunCopyOut", "NB_TeduhCapex_RunCopyJob", "GateGold", {"copy_job": "CJ_Status_Out"}), gate("CopyOut", "RunCopyOut")]
    pl = os.path.join(F, "PL_TeduhCapex_Nightly.DataPipeline")
    w(os.path.join(pl, "pipeline-content.json"), json.dumps({"properties": {"description": "P38 nightly: Dataverse to lake, ERP extract, Gold, Gold to Dataverse; a verdict gate after each step.",
        "activities": acts, "parameters": {"p_block_at": {"type": "string", "defaultValue": ""}}}}, indent=2) + "\n")
    platform(pl, "DataPipeline", "PL_TeduhCapex_Nightly", "P38 nightly: Copy in, ERP, Gold, Copy out; verdict gates (S179).")
    return res

if __name__ == "__main__":
    for r in build(): print(r)
    print("files", sum(len(fs) for _, _, fs in os.walk(F)))
