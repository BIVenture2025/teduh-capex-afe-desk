"""P38 T16, third place: evaluate the DEPLOYED flow's tier and total expressions (clientdata.json) on the oracle's 18 LOA
vectors. The two Compose texts are translated mechanically (if/lessOrEquals/add/float) into Python and evaluated; any
other function in them fails the test. Prints one line per vector and a verdict."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "01_Design", "src"))
from oracle import LOA_VECTORS, loa_tier
A = json.load(open(os.path.join(HERE, "clientdata.json")))["properties"]["definition"]["actions"]["Try"]["actions"]
tier_x, total_x = A["Tier"]["inputs"], A["AFE_total"]["inputs"]
def py(x):
    x = x.lstrip("@")
    x = x.replace("outputs('AFE_total')", "T").replace("variables('ApprovedSum')", "AP").replace("variables('PendingSum')", "PE")
    x = x.replace("float(triggerOutputs()?['body/tsc_amount'])", "RQ")
    left = re.sub(r"\b(if|lessOrEquals|add)\b|[TAPERQ0-9.,()' ]|T[123]", "", x)
    if left.strip(): raise SystemExit("untranslated tokens: %r" % left)
    return re.sub(r"\bif\(", "IF(", x)   # `if` is a Python keyword
F = {"IF": lambda c, a, b: a if c else b, "lessOrEquals": lambda a, b: a <= b, "add": lambda a, b: a + b}
tx, sx = py(tier_x), py(total_x)
ok = 0
for v in LOA_VECTORS:
    ap, pe, rq = v[0], v[1], v[2]
    t = eval(sx, {}, dict(F, AP=ap, PE=pe, RQ=rq))
    got = eval(tx, {}, dict(F, T=t))
    want = loa_tier(ap, pe, rq)
    want = want if isinstance(want, str) else want[0]
    exp = v[3]
    good = got == want == exp
    ok += good
    print("%-14s %-14s %-14s total %-14s flow %s oracle %s vector %s %s" % (ap, pe, rq, t, got, want, exp, "OK" if good else "MISMATCH"))
print("FLOW_RULE %d of %d %s" % (ok, len(LOA_VECTORS), "OK" if ok == len(LOA_VECTORS) else "FAIL"))
sys.exit(0 if ok == len(LOA_VECTORS) else 1)
