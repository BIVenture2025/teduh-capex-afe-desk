#!/usr/bin/env python3
"""P38 code app 'P38 AFE Spend' (review test 2). Runs on Windows through the P38 runner.
Scaffold: %USERPROFILE%\\p38_codeapp (pa app init done in the P3 probe). This folder holds the source of truth (src/*.tsx);
the scaffold is a build area.
Modes: addsrc  - pa app add data-source (native Dataverse: tsc_afestatus, tsc_afe) and copy src/generated back here for reading
       push    - copy ./src/*.tsx|*.css over the scaffold's src, npm run build, pa app push; print the play URL"""
import os, shutil, subprocess, sys
sys.stdout.reconfigure(encoding="ascii", errors="replace"); sys.stderr.reconfigure(encoding="ascii", errors="replace")  # the runner decodes cp1252
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.environ["USERPROFILE"], "p38_codeapp")
ORG = "https://<yourorg>.crm.dynamics.com"
def sh(cmd, timeout=900):
    p = subprocess.run(cmd, cwd=APP, shell=True, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    with open(os.path.join(HERE, "codeapp_log.txt"), "a", encoding="utf-8") as f:
        f.write("$ %s -> %s\n%s\n%s\n" % (cmd, p.returncode, p.stdout, p.stderr))
    print("$", cmd, "->", p.returncode); print(p.stdout[-6000:]); print(p.stderr[-3000:], file=sys.stderr)
    if p.returncode != 0: raise SystemExit("FAILED: " + cmd)
def addsrc():
    for t in ("tsc_afestatus", "tsc_afe"):
        sh("npx --no-install pa app add data-source --connector dataverse --table %s --org-url %s" % (t, ORG))
    gen = os.path.join(APP, "src", "generated"); dst = os.path.join(HERE, "generated_readback")
    os.makedirs(dst, exist_ok=True)
    n = 0
    for r, _, fs in os.walk(gen):
        for f in fs:
            rel = os.path.relpath(os.path.join(r, f), gen); out = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True); shutil.copyfile(os.path.join(r, f), out); n += 1
    for f in ("power.config.json", "package.json"):
        shutil.copyfile(os.path.join(APP, f), os.path.join(dst, "_" + f))
    print("generated files copied:", n)
def push():
    src = os.path.join(HERE, "src"); n = 0
    for f in os.listdir(src):
        if f.endswith((".tsx", ".ts", ".css")):
            shutil.copyfile(os.path.join(src, f), os.path.join(APP, "src", f)); n += 1
    print("source files copied:", n)
    sh("npm run build")
    sh("npx --no-install pa app push", timeout=1200)
if __name__ == "__main__":
    {"addsrc": addsrc, "push": push}[sys.argv[1]]()
    print("CODEAPP_STEP_OK", sys.argv[1])
