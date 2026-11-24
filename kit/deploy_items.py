#!/usr/bin/env python3
"""
deploy_items.py — deploy a folder of Fabric item definitions to a workspace
(Phase B of the Fabric readiness plan, 2026-08-20; fabric-cicd wrapper).

The engine's build loop is: author item definitions ON DISK -> validate
offline -> deploy through this tool -> verify by query against the live
estate. This wraps the official `fabric-cicd` library (the deployment tool
Microsoft documents as the standard for Fabric CI/CD) with the engine's
disciplines:

  * SCAN FLOOR (App C 24): counts the item folders it is about to deploy and
    refuses to run against zero — "deployed nothing, cleanly" must never
    read as success.
  * --whatif: lists exactly what WOULD deploy (item name, type, file count)
    and exits without touching the estate.
  * RECORD WHAT YOU RAN (App C 18): prints the resolved workspace, auth
    credential type, item-type scope and library version before acting.
  * Read-back reminder: deployment success is fabric-cicd's claim; the tool
    prints the fab-CLI command that verifies it independently.

Repository layout expected (fabric-cicd convention — each item is a folder
named `<DisplayName>.<Type>` containing its definition files):

    repo/
      MyLakehouse.Lakehouse/
      IngestSales.Notebook/notebook-content.py
      SM_Sales.SemanticModel/definition/...

Item types supported by the installed library (v askable via --list-types):
Lakehouse, Notebook, DataPipeline, Dataflow, Eventhouse, Eventstream,
KQLDatabase, KQLQueryset, KQLDashboard, Reflex, Ontology, DataAgent,
SemanticModel, Report, Warehouse, SQLDatabase, VariableLibrary,
UserDataFunction, Environment, SparkJobDefinition, CopyJob, GraphQLApi,
MirroredDatabase, MLExperiment, Map, PaginatedReport, and more.

Auth: AzureCliCredential by default (run `az login` once), falling back to
DefaultAzureCredential. `fab auth login` alone is NOT sufficient — the
Fabric CLI keeps its own token cache that this library cannot read.

Usage:
    python3 deploy_items.py <repo_dir> --workspace-name "P26-Dev" [--whatif]
    python3 deploy_items.py <repo_dir> --workspace-id <guid> \
        --types Notebook Lakehouse --environment PROD
    python3 deploy_items.py --list-types
    python3 deploy_items.py --selftest
"""
import argparse
import hashlib
import os
import re
import sys
import time
from pathlib import Path

ITEM_DIR_RE = re.compile(r"^(?P<name>.+)\.(?P<type>[A-Za-z][A-Za-z0-9]+)$")


def scan_repo(repo: Path):
    """Return [(display_name, item_type, file_count)] for item folders in repo."""
    found = []
    if not repo.is_dir():
        return found
    for child in sorted(repo.iterdir()):
        if not child.is_dir():
            continue
        m = ITEM_DIR_RE.match(child.name)
        if not m:
            continue
        n_files = sum(1 for _ in child.rglob("*") if _.is_file())
        found.append((m.group("name"), m.group("type"), n_files))
        # CHILD ITEMS (guide §196): Fabric Git stores some items INSIDE their parent, e.g. a KQL database at
        # <Name>.Eventhouse/.children/<Name>.KQLDatabase/. fabric-cicd discovers them (it walks every .platform),
        # but it publishes only types in item_type_in_scope, and that scope is derived from THIS list when
        # --types is not given. Missing them dropped KQLDatabase from scope on P30 S6b: the database was
        # never created and the Eventstream and Map that reference it failed ("not yet deployed").
        kids = child / ".children"
        if kids.is_dir():
            for g in sorted(kids.iterdir()):
                gm = ITEM_DIR_RE.match(g.name)
                if g.is_dir() and gm:
                    found.append((gm.group("name"), gm.group("type"),
                                  sum(1 for _ in g.rglob("*") if _.is_file())))
    return found


def split_scope(types, supported):
    """W4 (guide 212a): fabric-cicd validates EVERY type in scope before publishing anything, so one unsupported
    type (MLModel in 1.4.0) failed the whole P34 deploy with zero items written. Split the scope instead:
    returns (keep, skipped), both sorted. `supported` is the installed library's ItemType values."""
    sup = set(supported)
    keep = sorted(t for t in types if t in sup)
    skipped = sorted(t for t in types if t not in sup)
    return keep, skipped


def supported_types():
    try:
        from fabric_cicd import ItemType
    except ImportError:
        return None
    return [m.value for m in ItemType]


def selftest() -> int:
    import tempfile
    fails = 0
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # positive control: two well-formed item folders, one with a file
        (root / "NB1.Notebook").mkdir()
        (root / "NB1.Notebook" / "notebook-content.py").write_text("print(1)\n")
        (root / "LH.Lakehouse").mkdir()
        # false-positive controls: a plain folder and a loose file must NOT count
        (root / "docs").mkdir()
        (root / "readme.md").write_text("x")
        got = scan_repo(root)
        checks = [
            ("finds both item folders", len(got) == 2),
            ("reads the type from the suffix", {t for _, t, _ in got} == {"Notebook", "Lakehouse"}),
            ("counts files inside", dict((n, c) for n, _, c in got)["NB1"] == 1),
            ("empty item folder still listed (0 files)", dict((n, c) for n, _, c in got)["LH"] == 0),
        ]
        # CHILD-ITEM controls (guide §196). Positive: a KQL database nested under its Eventhouse is found and
        # its type enters scope. False positive: a .children folder under a NON-item folder, and a non-item
        # folder inside .children, add nothing.
        with tempfile.TemporaryDirectory() as td3:
            r3 = Path(td3)
            kq = r3 / "EH.Eventhouse" / ".children" / "EH.KQLDatabase"
            kq.mkdir(parents=True)
            (kq / "DatabaseSchema.kql").write_text(".create-merge table t (a:string)\n")
            (r3 / "EH.Eventhouse" / "EventhouseProperties.json").write_text("{}")
            (r3 / "EH.Eventhouse" / ".children" / "notes").mkdir()
            (r3 / "docs" / ".children" / "X.KQLDatabase").mkdir(parents=True)
            g3 = scan_repo(r3)
            checks.append(("child item found under <Parent>/.children/", ("EH", "KQLDatabase", 1) in g3))
            checks.append(("child type enters the derived scope", "KQLDatabase" in {t for _, t, _ in g3}))
            checks.append(("no extra items from non-item folders", len(g3) == 2))
        # SCOPE-SPLIT controls (guide 212a). Positive: an unsupported type leaves the scope and is reported.
        # False positive: an all-supported scope is returned whole, nothing skipped.
        k1, s1 = split_scope(["Notebook", "MLModel", "Lakehouse"], ["Notebook", "Lakehouse", "MLExperiment"])
        checks.append(("unsupported type is split out of scope", k1 == ["Lakehouse", "Notebook"] and s1 == ["MLModel"]))
        k2, s2 = split_scope(["Notebook", "Lakehouse"], ["Notebook", "Lakehouse", "MLExperiment"])
        checks.append(("all-supported scope kept whole, nothing skipped", k2 == ["Lakehouse", "Notebook"] and s2 == []))
        # scan-floor control: an empty repo returns nothing
        with tempfile.TemporaryDirectory() as td2:
            checks.append(("empty repo -> zero items", scan_repo(Path(td2)) == []))
        for label, ok in checks:
            print(f"  [{'ok' if ok else 'FAIL'}] {label}")
            fails += not ok
    print(f"[scan] selftest ran {len(checks)} controls")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", nargs="?", help="folder holding <Name>.<Type> item definition folders")
    ap.add_argument("--workspace-id", default=None, help="target workspace GUID")
    ap.add_argument("--workspace-name", default=None, help="target workspace display name")
    ap.add_argument("--types", nargs="*", default=None,
                    help="item types in scope, e.g. Notebook Lakehouse (default: types present in repo)")
    ap.add_argument("--environment", default="N/A", help="variable-library value-set / parameter environment")
    ap.add_argument("--whatif", action="store_true", help="list what would deploy, touch nothing")
    ap.add_argument("--unpublish-orphans", action="store_true",
                    help="after publishing, remove workspace items absent from the repo (DESTRUCTIVE - grep names first, App C 27)")
    ap.add_argument("--list-types", action="store_true", help="print the installed library's supported item types")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    if a.list_types:
        try:
            from fabric_cicd import ItemType
        except ImportError:
            print("[FAIL] fabric-cicd not installed (command run: import fabric_cicd). pip install fabric-cicd")
            return 2
        for m in ItemType:
            print(f"  {m.value}")
        return 0

    if not a.repo:
        ap.error("repo is required (or use --list-types / --selftest)")
    repo = Path(a.repo).resolve()

    # ---- scan first: the floor -------------------------------------------
    items = scan_repo(repo)
    print(f"[scan] {len(items)} item folder(s) under {repo}")
    for name, typ, nf in items:
        print(f"   {name:40} {typ:22} {nf} file(s)")
    if not items:
        print("[!!] ZERO item folders found - refusing to run. A deploy of nothing must never")
        print("     look like a deploy (App C 24). Expected folders named <Name>.<Type>.")
        return 3
    empty = [n for n, _, nf in items if nf == 0]
    if empty:
        print(f"[!!] {len(empty)} item folder(s) have NO files: {', '.join(empty)} - they will fail or deploy empty.")

    types_in_scope = a.types if a.types else sorted({t for _, t, _ in items})
    sup = supported_types()
    if sup is None:
        print("[plan] fabric-cicd not importable here: scope not checked against the library's item types")
    else:
        try:
            from importlib.metadata import version as _v
            libv = _v("fabric-cicd")
        except Exception:  # noqa: BLE001
            libv = "?"
        types_in_scope, skipped = split_scope(types_in_scope, sup)
        if skipped:
            sk_items = [f"{n}.{t}" for n, t, _ in items if t in skipped]
            print(f"[skip] fabric-cicd {libv} does not support type(s) {', '.join(skipped)}: "
                  f"{len(sk_items)} item(s) NOT deployed by this tool: {', '.join(sk_items)}")
            print("[skip] create them another way (MLModel: an empty item by REST or Core MCP; the training "
                  "notebook then registers versions, SETTLED S154) and count them in the read-back")
        if not types_in_scope:
            print("[!!] no supported type left in scope - refusing to run")
            return 3
    print(f"[plan] types in scope: {', '.join(types_in_scope)}  environment: {a.environment}")

    if a.whatif:
        print("[whatif] nothing deployed. Re-run without --whatif to publish.")
        return 0

    if not a.workspace_id and not a.workspace_name:
        print("[FAIL] --workspace-id or --workspace-name is required to deploy.")
        return 2

    # ---- deploy ----------------------------------------------------------
    try:
        from fabric_cicd import FabricWorkspace, publish_all_items, unpublish_all_orphan_items
    except ImportError:
        print("[FAIL] fabric-cicd not installed (command run: import fabric_cicd). pip install fabric-cicd")
        return 2
    try:
        from azure.identity import AzureCliCredential, DefaultAzureCredential
        cred = AzureCliCredential()
        try:
            cred.get_token("https://api.fabric.microsoft.com/.default")
            cred_name = "AzureCliCredential (az login)"
        except Exception:  # noqa: BLE001
            cred = DefaultAzureCredential()
            cred_name = "DefaultAzureCredential"
    except ImportError:
        print("[FAIL] azure-identity not installed. pip install azure-identity")
        return 2

    print(f"[auth] credential: {cred_name}")
    print(f"[target] workspace_id={a.workspace_id or '-'} workspace_name={a.workspace_name or '-'}")

    ws = FabricWorkspace(
        repository_directory=str(repo),
        token_credential=cred,
        item_type_in_scope=types_in_scope,
        environment=a.environment,
        workspace_id=a.workspace_id,
        workspace_name=a.workspace_name,
    )
    result = publish_all_items(ws)
    print(f"[done] publish_all_items returned: {result if result is not None else 'completed (no result payload)'}")

    if a.unpublish_orphans:
        print("[orphans] removing workspace items absent from the repo...")
        r2 = unpublish_all_orphan_items(ws)
        print(f"[done] unpublish_all_orphan_items returned: {r2 if r2 is not None else 'completed'}")

    tgt = a.workspace_name or a.workspace_id
    print()
    print("[verify] deployment success above is the library's claim. Read it back yourself:")
    print(f"    fab ls \"{tgt}.Workspace\"")
    print("  and count the listing against the item table at the top of this run.")
    return 0


def _self_stamp():
    p = os.path.abspath(__file__)
    h = hashlib.sha1(open(p, "rb").read()).hexdigest()[:10]
    m = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(p)))
    print(f"[tool] {os.path.basename(p)} sha1={h} mtime={m} path={p}", file=sys.stderr)


if __name__ == "__main__":
    _self_stamp()
    sys.exit(main())
