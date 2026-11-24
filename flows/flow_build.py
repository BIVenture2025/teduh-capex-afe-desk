"""flow_build.py - P38 'P38 AFE approval' solution flow (Dataverse workflow row clientdata), built with flow_kit and linted.
Trigger: tsc_afe created or updated with status Submitted. Finance check, then the LOA tier on the AFE total
(approved family + supplements in approval + this request; contract in the Implementation Guide), write back, email.
A supplement to a Closed or Rejected original is refused. Any failure sets status 'Needs attention'.
Writes clientdata.json beside this file."""
import json, os, sys
ENGINE = os.environ.get("ENGINE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "_ENGINE"))
sys.path.insert(0, os.path.join(ENGINE, "templates", "powerapps", "flows"))
from flow_kit import compose, send_email_v2, start_and_wait_approval, definition, lint_flow, chain
DV = "shared_commondataserviceforapps"
A = "/providers/Microsoft.PowerApps/apis/" + DV
def dv(name, op, params, after=None):
    return name, {"runAfter": ({after: ["Succeeded"]} if isinstance(after, str) else (after or {})), "type": "OpenApiConnection",
                  "inputs": {"host": {"apiId": A, "connectionName": DV, "operationId": op}, "parameters": params, "authentication": "@parameters('$authentication')"}}
TB = "triggerOutputs()?['body/%s']"
t = lambda c: "@" + TB % c
ti = lambda c: "@{" + TB % c + "}"
TODAY = "@{formatDateTime(utcNow(), 'yyyy-MM-dd')}"
def upd(name, cols, after=None):
    p = {"entityName": "tsc_afes", "recordId": t("tsc_afeid")}; p.update({"item/" + k: v for k, v in cols.items()}); return dv(name, "UpdateRecord", p, after)
def decision(name, step, role, approver, submitted, outcome, comment, after=None):
    return dv(name, "CreateRecord", {"entityName": "tsc_afedecisions", "item/tsc_name": "%s %s @{ticks(utcNow())}" % (ti("tsc_afeno"), step),
              "item/tsc_afeno": t("tsc_afeno"), "item/tsc_step": step, "item/tsc_role": role, "item/tsc_approveremail": approver,
              "item/tsc_submittedon": submitted, "item/tsc_decidedon": TODAY, "item/tsc_outcome": outcome, "item/tsc_comment": comment}, after)
def iff(name, expr, yes, no, after=None):
    return name, {"runAfter": ({after: ["Succeeded"]} if after else {}), "type": "If", "expression": expr,
                  "actions": dict(chain(*yes)), "else": {"actions": dict(chain(*no))}}
def mail(name, subject, body, after=None):
    return send_email_v2(name, t("tsc_requesteremail"), subject, body, after)
first = lambda a, c: "first(outputs('%s')?['body/value'])?['%s']" % (a, c)
CMT1 = "@{coalesce(first(outputs('Approval_Finance')?['body/responses'])?['comments'], '')}"
CMT2 = "@{coalesce(first(outputs('Approval_LOA')?['body/responses'])?['comments'], '')}"
WHO = "@{outputs('Approver_role')}"

trigger = {"When_an_AFE_is_submitted": {"type": "OpenApiConnectionWebhook", "inputs": {
    "host": {"apiId": A, "connectionName": DV, "operationId": "SubscribeWebhookTrigger"},
    "parameters": {"subscriptionRequest/message": 4, "subscriptionRequest/entityname": "tsc_afe", "subscriptionRequest/scope": 4,
                   "subscriptionRequest/filteringattributes": "tsc_status", "subscriptionRequest/filterexpression": "tsc_status eq 'Submitted'"},
    "authentication": "@parameters('$authentication')"}}}

P = "@{outputs('Family_key')}"
try_steps = [
    compose("Family_key", "@if(equals(%s, 'Supplement'), %s, %s)" % (TB % "tsc_kind", TB % "tsc_parentafeno", TB % "tsc_afeno")),
    dv("Get_original", "ListRecords", {"entityName": "tsc_afes", "$filter": "tsc_afeno eq '%s'" % P, "$top": 1}),
    dv("Get_family_approved", "ListRecords", {"entityName": "tsc_afes", "$select": "tsc_amount",
       "$filter": "(tsc_afeno eq '%s' or tsc_parentafeno eq '%s') and (tsc_status eq 'Approved' or tsc_status eq 'Closed')" % (P, P)}),
    dv("Get_family_pending", "ListRecords", {"entityName": "tsc_afes", "$select": "tsc_amount",
       "$filter": "tsc_parentafeno eq '%s' and tsc_afeno ne '%s' and (tsc_status eq 'Submitted' or tsc_status eq 'Finance check' or tsc_status eq 'LOA approval')" % (P, ti("tsc_afeno"))}),
    ("Sum_approved", {"runAfter": {}, "type": "Foreach", "foreach": "@outputs('Get_family_approved')?['body/value']",
                      "actions": {"Add_approved": {"runAfter": {}, "type": "IncrementVariable", "inputs": {"name": "ApprovedSum", "value": "@float(items('Sum_approved')?['tsc_amount'])"}}}}),
    ("Sum_pending", {"runAfter": {}, "type": "Foreach", "foreach": "@outputs('Get_family_pending')?['body/value']",
                     "actions": {"Add_pending": {"runAfter": {}, "type": "IncrementVariable", "inputs": {"name": "PendingSum", "value": "@float(items('Sum_pending')?['tsc_amount'])"}}}}),
    compose("AFE_total", "@add(add(variables('ApprovedSum'), variables('PendingSum')), float(%s))" % (TB % "tsc_amount")),
    compose("Tier", "@if(lessOrEquals(outputs('AFE_total'), 5000000), 'T1', if(lessOrEquals(outputs('AFE_total'), 25000000), 'T2', 'T3'))"),
    dv("Get_FIN", "ListRecords", {"entityName": "tsc_loatiers", "$filter": "tsc_tiercode eq 'FIN'", "$top": 1}),
    dv("Get_tier_row", "ListRecords", {"entityName": "tsc_loatiers", "$filter": "tsc_tiercode eq '@{outputs('Tier')}'", "$top": 1}),
    dv("Get_asset", "ListRecords", {"entityName": "tsc_assets", "$filter": "tsc_assetcode eq '%s'" % ti("tsc_assetcode"), "$top": 1}),
    dv("Get_budget", "ListRecords", {"entityName": "tsc_assetbudgets", "$filter": "tsc_assetcode eq '%s' and tsc_year eq @{int(formatDateTime(utcNow(), 'yyyy'))}" % ti("tsc_assetcode"), "$top": 1}),
    compose("Approver2", "@if(equals(outputs('Tier'), 'T1'), %s, %s)" % (first("Get_asset", "tsc_manageremail"), first("Get_tier_row", "tsc_approveremail"))),
    compose("Approver_role", "@if(equals(outputs('Tier'), 'T1'), 'Asset manager', %s)" % first("Get_tier_row", "tsc_approverrole")),
    compose("Details", "**%s** %s\n\nAsset: %s · Kind: %s\n\nThis request: RM @{formatNumber(float(%s), 'N2')} · AFE total after it: RM @{formatNumber(outputs('AFE_total'), 'N2')} · Tier @{outputs('Tier')}\n\n"
            "Asset capex @{formatDateTime(utcNow(), 'yyyy')}: budget RM @{formatNumber(float(coalesce(%s, 0)), 'N0')}, actual RM @{formatNumber(float(coalesce(%s, 0)), 'N0')}, left RM @{formatNumber(float(coalesce(%s, 0)), 'N0')}\n\nReason: %s\n\nFictional company, synthetic data."
            % (ti("tsc_afeno"), ti("tsc_title"), ti("tsc_assetcode"), ti("tsc_kind"), TB % "tsc_amount", first("Get_budget", "tsc_budget"), first("Get_budget", "tsc_actual"), first("Get_budget", "tsc_left"), ti("tsc_justification"))),
    iff("Refuse_if_original_closed", {"and": [{"equals": [t("tsc_kind"), "Supplement"]}, {"or": [{"equals": ["@" + first("Get_original", "tsc_status"), "Closed"]}, {"equals": ["@" + first("Get_original", "tsc_status"), "Rejected"]}]}]},
        [upd("Refuse", {"tsc_status": "Rejected", "tsc_decidedon": TODAY, "tsc_lastcomment": "Refused: the original AFE is @{%s}." % first("Get_original", "tsc_status")}),
         mail("Mail_refused", "Supplement %s refused" % ti("tsc_afeno"), "<p>A supplement cannot be raised on an original that is Closed or Rejected.</p>"),
         ("Stop_refused", {"runAfter": {}, "type": "Terminate", "inputs": {"runStatus": "Succeeded"}})],
        []),
    upd("Set_finance_check", {"tsc_status": "Finance check", "tsc_loatier": "@{outputs('Tier')}"}),
    start_and_wait_approval("Approval_Finance", "Finance check: %s %s" % (ti("tsc_afeno"), ti("tsc_title")), "@{%s}" % first("Get_FIN", "tsc_approveremail"), "@{outputs('Details')}"),
    compose("Finance_decided_on", TODAY),
    iff("Finance_passed", {"equals": ["@outputs('Approval_Finance')?['body/outcome']", "Approve"]},
        [decision("Log_finance_passed", "Finance check", "Finance controller", "@{%s}" % first("Get_FIN", "tsc_approveremail"), ti("tsc_submittedon"), "Passed", CMT1),
         upd("Set_loa", {"tsc_status": "LOA approval"}),
         start_and_wait_approval("Approval_LOA", "Approve (%s): %s %s" % ("@{outputs('Tier')}", ti("tsc_afeno"), ti("tsc_title")), "@{outputs('Approver2')}", "@{outputs('Details')}\n\nFinance check: passed."),
         iff("LOA_approved", {"equals": ["@outputs('Approval_LOA')?['body/outcome']", "Approve"]},
             [decision("Log_approved", "LOA approval", WHO, "@{outputs('Approver2')}", "@{outputs('Finance_decided_on')}", "Approved", CMT2),
              upd("Set_approved", {"tsc_status": "Approved", "tsc_decidedon": TODAY, "tsc_lastcomment": CMT2}),
              mail("Mail_approved", "AFE %s approved" % ti("tsc_afeno"), "<p>%s (%s) was approved by the %s.</p><p>%s</p>" % (ti("tsc_afeno"), ti("tsc_title"), WHO, CMT2))],
             [decision("Log_rejected", "LOA approval", WHO, "@{outputs('Approver2')}", "@{outputs('Finance_decided_on')}", "Rejected", CMT2),
              upd("Set_rejected", {"tsc_status": "Rejected", "tsc_decidedon": TODAY, "tsc_lastcomment": CMT2}),
              mail("Mail_rejected", "AFE %s rejected" % ti("tsc_afeno"), "<p>%s was rejected by the %s.</p><p>%s</p>" % (ti("tsc_afeno"), WHO, CMT2))])],
        [decision("Log_returned", "Finance check", "Finance controller", "@{%s}" % first("Get_FIN", "tsc_approveremail"), ti("tsc_submittedon"), "Returned", CMT1),
         upd("Set_returned", {"tsc_status": "Returned", "tsc_lastcomment": CMT1}),
         mail("Mail_returned", "AFE %s returned by finance" % ti("tsc_afeno"), "<p>Finance returned %s. Edit it in the app and submit again.</p><p>%s</p>" % (ti("tsc_afeno"), CMT1))]),
]
actions = [
    ("Init_approved", {"runAfter": {}, "type": "InitializeVariable", "inputs": {"variables": [{"name": "ApprovedSum", "type": "float", "value": 0}]}}),
    ("Init_pending", {"runAfter": {"Init_approved": ["Succeeded"]}, "type": "InitializeVariable", "inputs": {"variables": [{"name": "PendingSum", "type": "float", "value": 0}]}}),
    ("Try", {"runAfter": {"Init_pending": ["Succeeded"]}, "type": "Scope", "actions": dict(chain(*try_steps))}),
    upd("Needs_attention", {"tsc_status": "Needs attention", "tsc_lastcomment": "The approval flow failed; see its run history."}, {"Try": ["Failed", "TimedOut"]}),
]
d = definition(trigger, actions, conns=[DV, "shared_approvals", "shared_office365"], prefix="tsc")
issues = lint_flow(d)
json.dump(d, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "clientdata.json"), "w"), indent=1)
print("lint", issues if issues else "clean", "| actions in Try", len(try_steps))
