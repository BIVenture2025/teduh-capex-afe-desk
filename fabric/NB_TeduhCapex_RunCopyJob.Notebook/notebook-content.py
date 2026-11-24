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

# NB_TeduhCapex_RunCopyJob (P38)
#
# Runs one Copy job by name and waits (the pipeline Copy job activity needs a portal connection, S178).

# PARAMETERS CELL ********************

copy_job = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# P38: run one Copy job on demand (Fabric job API, jobType=Execute) and wait (P34 shape, S178).
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

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
