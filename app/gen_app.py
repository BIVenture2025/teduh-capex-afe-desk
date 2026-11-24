#!/usr/bin/env python3
"""P38 canvas app 'Teduh Capex': .pa.yaml generated from the engine kit (pa_yaml builders, kit components, the
responsive screen templates scrTplHome / scrTplFormSteps / scrTplListDetail as the layout source). Edit this file, never the YAML.
Usage: python3 gen_app.py <kit dir: _ENGINE/templates/powerapps> <out dir>"""
import json, os, shutil, sys
KIT, OUT = sys.argv[1:3]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
sys.path.insert(0, os.path.join(HERE, "..", "..", "01_Design", "src"))
from pa_yaml import (app, button, container, dropdown, gallery, instance, number_input, screen, text, timer, text_input, date_picker, write_app)  # noqa: E402
from oracle import LOA_VECTORS, loa_tier  # noqa: E402

AF, ST, LN, PH, DC, AS, LT = "AFEs", "'AFE statuses'", "'AFE lines'", "'AFE phasing'", "'AFE decisions'", "Assets", "'LOA tiers'"
PAD = "If(nfIsMobile, nfSpace.Md, nfSpace.Xxl)"
TOUCH = "nfSize.Touch"
GROW = "If(nfIsMobile, 1, 0)"
TILE_W = "If(nfIsMobile, Parent.Width, If(nfIsDesktop, (Parent.Width - 2 * nfSpace.Md) / 3, (Parent.Width - nfSpace.Md) / 2))"
RAD = dict(RadiusTopLeft="nfRadius.Pill", RadiusTopRight="nfRadius.Pill", RadiusBottomLeft="nfRadius.Pill", RadiusBottomRight="nfRadius.Pill")
FOOT = '"Teduh Samudera Energy is fictional · synthetic data"'
KIND = '{s}'
STKIND = 'Switch({s}, "Approved", "Info", "Closed", "Neutral", "Rejected", "Danger", "Needs attention", "Danger", "Returned", "Warn", "Warn")'
FILL = 'Switch({k}, "Success", nfColor.SuccessFill, "Warn", nfColor.WarnFill, "Danger", nfColor.DangerFill, "Info", nfColor.InfoFill, nfColor.NeutralFill)'
TXT = 'Switch({k}, "Success", nfColor.SuccessText, "Warn", nfColor.WarnText, "Danger", nfColor.DangerText, "Info", nfColor.InfoText, nfColor.NeutralText)'
LABEL = 'If({s} = "Approved", "In progress", {s})'

tokens = open(os.path.join(HERE, "theme", "PitchSidePro_Theme_v2_Executive.AppFormulas.fx"), encoding="utf-8").read()
core = open(os.path.join(KIT, "powerfx", "nf_core.fx"), encoding="utf-8").read()
vrows = ",\n    ".join('{{ A: {a}, P: {p}, R: {r}, Tier: "{t}" }}'.format(a=a, p=p, r=r, t=t) for a, p, r, t in LOA_VECTORS)
assert all(loa_tier(a, p, r) == t for a, p, r, t in LOA_VECTORS)
rules = f"""
// ---- P38 LOA rule (contract: Design Package guide, tab 'LOA rule'; oracle 01_Design/src/oracle.py) ----
tcTier(total: Number): Text = If(Round(total, 2) <= 5000000, "T1", Round(total, 2) <= 25000000, "T2", "T3");
tcTierText(t: Text): Text = Switch(t, "T1", "Asset manager (T1, up to RM 5m)", "T2", "GM Projects (T2, over RM 5m and up to RM 25m)", "CEO (T3, over RM 25m)");
tcMoney(v: Number): Text = If(v < 0, "-", "") & If(Abs(v) < 1000000, "RM " & Text(Abs(v) / 1000, "#,##0") & "k", "RM " & Text(Abs(v) / 1000000, "#,##0.0") & "m");
tcPrefix = "TSE-AFE-" & Text(Today(), "yy") & "-";
tcVectors = Table(
    {vrows}
);
"""
formulas = tokens + "\n" + core + "\n" + rules

def header(name, title, sub, back=True, onback="Navigate(scrHome, ScreenTransition.None)"):
    return instance(name, "cmpPageHeader", dict(Title=title, Subtitle=sub, ShowBack="true" if back else "false", OnBack=onback,
                    AlignInContainer="AlignInContainer.Stretch", LayoutMinHeight=56, FillPortions=0, Height="If(nfIsMobile, 64, 88)"))
def foot(name):
    return text(name, FOOT, size="nfType.Micro", color="nfColor.TextMuted", Align="Align.Center", AccessibleLabel=FOOT, AutoHeight="true", AlignInContainer="AlignInContainer.Stretch")
def cap(name, t, **kw):
    return text(name, f'"{t}"', size="nfType.Caption", weight="Semibold", color="nfColor.TextMuted", AccessibleLabel=f'"{t}"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch", **kw)
def pill(name, status, **kw):
    k = STKIND.format(s=status)
    return text(name, LABEL.format(s=status), size="nfType.Caption", weight="Semibold", color=TXT.format(k=k), Fill=FILL.format(k=k),
                AccessibleLabel=f'"Status: " & {status}', Align="Align.Center", VerticalAlign="VerticalAlign.Middle", Height=28, Width=150,
                PaddingTop=0, PaddingBottom=0, LayoutMinHeight=28, Wrap="false", **RAD, **kw)
def toast(prefix):
    return [instance(f"cmp{prefix}Toast", "cmpToast", dict(Show="locToast", Visible="locToast", Kind="locToastKind", Message="locToastMsg",
                     OnDismiss="UpdateContext({ locToast: false })", Width="Min(480, Parent.Width - 2 * nfSpace.Lg)", Height="nfSize.RowLg",
                     X="(Parent.Width - Self.Width) / 2", Y="Parent.Height - Self.Height - nfSpace.Xxl")),
            timer(f"tmr{prefix}Toast", 4000, on_end="UpdateContext({ locToast: false })", Start="locToast", AutoStart="locToast", Repeat="false", Reset="true")]

MINE = f'FirstN(Sort(Filter({AF}, \'Requester email\' = User().Email && Kind = "Original"), \'AFE no\', SortOrder.Descending), 500)'
OPEN_ST = 'tsc_status = "Submitted" || tsc_status = "Finance check" || tsc_status = "LOA approval"'
FLAGS = f"Filter(FirstN(Filter({ST}, 'Supplement needed' = true), 500), !IsBlank(LookUp({AF}, 'AFE no' = ThisRecord.'AFE no' && 'Requester email' = User().Email)))"

# ---------------------------------------------------------------- 1 Home
kpi = lambda nm, title, val, capn: instance(nm, "cmpKpiTile", dict(Title=f'"{title}"', Value=f'Text({val}, "#,##0")', Caption=capn, Kind='"Neutral"', Width=TILE_W, Height=104))
flag_row = [container("cntHmFlag", "Horizontal", [
    text("txtHmFlag", "ThisItem.'AFE no' & \" is heading over approval: EAC \" & tcMoney(ThisItem.'EAC (RM)') & \" against \" & tcMoney(ThisItem.'Approved (RM)') & \" approved.\"",
         color="nfColor.DangerText", AccessibleLabel="\"Supplement needed for \" & ThisItem.'AFE no'", FillPortions=1, AlignInContainer="AlignInContainer.Stretch"),
    button("btnHmFlag", '"Raise supplement"', "Set(gblParent, LookUp(AFEs, 'AFE no' = ThisItem.'AFE no')); Navigate(scrNew, ScreenTransition.None)",
           appearance="Outline", accessible="\"Raise a supplement for \" & ThisItem.'AFE no'", Height=TOUCH, Width=180),
], gap="nfSpace.Sm", pad="nfSpace.Sm", fill="nfColor.DangerFill", Width="Parent.TemplateWidth", Height="Parent.TemplateHeight", LayoutAlignItems="LayoutAlignItems.Center")]
home_main = container("cntHmMain", "Vertical", [
    container("cntHmKpis", "Horizontal", [
        kpi("cmpHmKpiOpen", "My AFEs in progress", f'CountRows(Filter({MINE}, tsc_status = "Approved"))', '"Approved and spending"'),
        kpi("cmpHmKpiFlag", "Need a supplement", f"CountRows({FLAGS})", '"EAC over 110% of approval"'),
        kpi("cmpHmKpiWait", "Waiting for a decision", f"CountRows(Filter({MINE}, {OPEN_ST}))", '"Finance check or LOA approval"'),
    ], gap="nfSpace.Md", LayoutWrap="true", AlignInContainer="AlignInContainer.Stretch", FillPortions=0,
        Height="If(nfIsMobile, 3 * 104 + 2 * nfSpace.Md, If(nfIsDesktop, 104, 2 * 104 + nfSpace.Md))"),
    container("cntHmActions", "Horizontal", [
        button("btnHmNew", '"New AFE"', "Set(gblParent, Blank()); Navigate(scrNew, ScreenTransition.None)", accessible='"Raise a new AFE"', icon="Add",
               Height=TOUCH, FillPortions=GROW, Width=160),
        button("btnHmMine", '"My AFEs"', "Set(gblSel, Blank()); Navigate(scrMine, ScreenTransition.None)", appearance="Outline", accessible='"Open my AFEs"', Height=TOUCH, FillPortions=GROW, Width=160),
        button("btnHmSpend", '"Spend"', 'Launch("https://apps.powerapps.com/play/e/<your-environment-id>/app/<your-code-app-id>")', appearance="Outline",
               accessible='"Open the spend screen (code app)"', Height=TOUCH, FillPortions=GROW, Width=160),
    ], gap="nfSpace.Sm", LayoutDirection="If(nfIsMobile, LayoutDirection.Vertical, LayoutDirection.Horizontal)", AlignInContainer="AlignInContainer.Stretch",
        FillPortions=0, Height="If(nfIsMobile, 3 * nfSize.Touch + 2 * nfSpace.Sm, nfSize.Touch)"),
    gallery("galHmFlags", FLAGS, flag_row, '"AFEs that need a supplement"', template_size="If(nfIsMobile, 110, 64)", FillPortions=1, AlignInContainer="AlignInContainer.Stretch"),
    foot("txtHmFoot"),
], gap="nfSpace.Lg", FillPortions=1, AlignInContainer="AlignInContainer.Stretch", LayoutOverflowY="LayoutOverflow.Scroll")   # 4th flag row was clipped (E2E 24 Nov)
scr_home = screen("scrHome", [container("cntHmRoot", "Vertical", [
    header("cmpHmHeader", '"Teduh Capex"', '"Hello " & User().FullName & ". Raise AFEs and follow their spend."', back=False, onback="false"),
    container("cntHmBody", "Horizontal", [home_main], gap="nfSpace.Xxl", pad=PAD, FillPortions=1, AlignInContainer="AlignInContainer.Stretch", LayoutMaxWidth="nfPageMaxW"),
], gap=0, fill="nfColor.Canvas", Width="Parent.Width", Height="Parent.Height", LayoutAlignItems="LayoutAlignItems.Center")], Fill="nfColor.Canvas")

# ---------------------------------------------------------------- 2 New AFE / supplement (scrTplFormSteps)
SUP = "!IsBlank(gblParent)"
y1, y2 = "Year(dteNwStart.SelectedDate)", "Year(dteNwStart.SelectedDate) + 1"
fam_appr = f"Coalesce(Sum(Filter({AF}, ('AFE no' = gblParent.'AFE no' || 'Parent AFE no' = gblParent.'AFE no') && (tsc_status = \"Approved\" || tsc_status = \"Closed\")), 'Amount (RM)'), 0)"
fam_pend = f"Coalesce(Sum(Filter({AF}, 'Parent AFE no' = gblParent.'AFE no' && ({OPEN_ST})), 'Amount (RM)'), 0)"
total = f"If({SUP}, {fam_appr} + {fam_pend} + numNwSup.Value, Coalesce(Sum(colEst, Total), 0))"
gst = f"LookUp({ST}, 'AFE no' = gblParent.'AFE no')"
est_row = [container("cntNwEstRow", "Horizontal", [
    text("txtNwEstName", "ThisItem.Name", AccessibleLabel="ThisItem.Name", FillPortions=1, AlignInContainer="AlignInContainer.Stretch", VerticalAlign="VerticalAlign.Middle"),
    number_input("numNwEstT", '"Total RM for " & ThisItem.Name', default="ThisItem.Total", Width=130, Height=TOUCH,
                 OnChange="Patch(colEst, ThisItem, { Total: Self.Value })"),
    number_input("numNwEstY1", '"First year RM for " & ThisItem.Name', default="ThisItem.Y1", Width=130, Height=TOUCH,
                 OnChange="Patch(colEst, ThisItem, { Y1: Self.Value })"),
    number_input("numNwEstY2", '"Second year RM for " & ThisItem.Name', default="ThisItem.Y2", Width=130, Height=TOUCH,
                 OnChange="Patch(colEst, ThisItem, { Y2: Self.Value })"),
], gap="nfSpace.Xs", Width="Parent.TemplateWidth", Height="Parent.TemplateHeight", LayoutAlignItems="LayoutAlignItems.Center")]
ok1 = "!IsBlank(drpNwAsset.Selected) && !IsBlank(drpNwType.Selected) && Len(Trim(txtNwTitle.Text)) >= 10 && !IsBlank(dteNwStart.SelectedDate) && dteNwEnd.SelectedDate > dteNwStart.SelectedDate"
ok2 = "Coalesce(Sum(colEst, Total), 0) > 0 && CountRows(Filter(colEst, Abs(Y1 + Y2 - Total) > 0.005)) = 0"
okS = f"numNwSup.Value > 0 && !({SUP} && (gblParent.tsc_status = \"Closed\" || gblParent.tsc_status = \"Rejected\"))"
step_pill = lambda n, t: text(f"txtNwStep{n}", f'"{n}. {t}"', size="nfType.Small", weight="Semibold", color=f"If(locStep >= {n}, nfColor.TextOnPrimary, nfColor.TextMuted)",
                              Fill=f"If(locStep >= {n}, nfColor.Primary, nfColor.NeutralFill)", AccessibleLabel=f'"Step {n}, {t}" & If(locStep = {n}, ", current", "")',
                              Align="Align.Center", VerticalAlign="VerticalAlign.Middle", Height="nfSize.RowSm", FillPortions=1, Wrap="false", **RAD)
step1 = container("cntNwStep1", "Vertical", [
    cap("txtNwAssetCap", "Asset"), dropdown("drpNwAsset", f"Sort({AS}, 'Asset code')", "ThisItem.'Asset name'", '"Asset, required"', AlignInContainer="AlignInContainer.Stretch", Height=TOUCH),
    cap("txtNwTypeCap", "AFE type"), dropdown("drpNwType", '["Drilling", "Facilities", "Pipeline", "IT and buildings", "Study"]', "ThisItem.Value", '"AFE type, required"', AlignInContainer="AlignInContainer.Stretch", Height=TOUCH),
    cap("txtNwTitleCap", "Title (at least 10 characters)"), text_input("txtNwTitle", '"Teduh Selatan water injection pump upgrade"', '"Title, required"', AlignInContainer="AlignInContainer.Stretch", Height=TOUCH),
    cap("txtNwDatesCap", "Planned start and end"),
    container("cntNwDates", "Horizontal", [date_picker("dteNwStart", '"Planned start"', Height=TOUCH, FillPortions=1), date_picker("dteNwEnd", '"Planned end"', Height=TOUCH, FillPortions=1)],
              gap="nfSpace.Sm", AlignInContainer="AlignInContainer.Stretch", FillPortions=0, Height=TOUCH),
    text("txtNwNoHint", '"The AFE number is given on submit (next: " & tcPrefix & "...)."', size="nfType.Small", color="nfColor.TextMuted", AccessibleLabel='"The AFE number is given on submit"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch"),
], gap="nfSpace.Sm", Visible=f"!{SUP} && locStep = 1", AlignInContainer="AlignInContainer.Stretch", FillPortions=1, LayoutOverflowY="LayoutOverflow.Scroll")
step2 = container("cntNwStep2", "Vertical", [
    text("txtNwEstHead", f'"Cost element · Total RM · " & {y1} & " · " & {y2}', size="nfType.Small", weight="Semibold", color="nfColor.TextMuted", AccessibleLabel='"Estimate columns"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch"),
    gallery("galNwEst", "colEst", est_row, '"Estimate by cost element"', template_size=56, FillPortions=1, AlignInContainer="AlignInContainer.Stretch"),
    text("txtNwEstTot", '"Total " & tcMoney(Coalesce(Sum(colEst, Total), 0)) & " · contingency " & Text(If(Coalesce(Sum(colEst, Total), 0) = 0, 0, LookUp(colEst, Code = "CON").Total / Coalesce(Sum(colEst, Total), 0)), "0%")',
         weight="Semibold", AccessibleLabel='"Estimate total"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch"),
], gap="nfSpace.Sm", Visible=f"!{SUP} && locStep = 2", AlignInContainer="AlignInContainer.Stretch", FillPortions=1)
route = f'"Who will decide: 1. Finance controller (budget check), then 2. " & tcTierText(tcTier({total})) & ". AFE total after this request: " & tcMoney({total}) & "."'
step3 = container("cntNwStep3", "Vertical", [
    text("txtNwSum", f'"Total " & tcMoney(Coalesce(Sum(colEst, Total), 0)) & ": " & {y1} & " " & tcMoney(Coalesce(Sum(colEst, Y1), 0)) & ", " & {y2} & " " & tcMoney(Coalesce(Sum(colEst, Y2), 0))', weight="Semibold", AccessibleLabel='"Total and phasing"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch"),
], gap="nfSpace.Sm", Visible=f"!{SUP} && locStep = 3", AlignInContainer="AlignInContainer.Stretch", FillPortions=0, Height=40)
supbox = container("cntNwSup", "Vertical", [
    text("txtNwSupParent", "\"Original AFE: \" & gblParent.'AFE no' & \" · \" & gblParent.Title", weight="Semibold", AccessibleLabel='"Original AFE"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch"),
    text("txtNwSupFacts", f"\"Approved so far \" & tcMoney({fam_appr}) & \" · EAC \" & tcMoney({gst}.'EAC (RM)')", color="nfColor.TextBody", AccessibleLabel='"Approved so far and EAC"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch"),
    text("txtNwSupClosed", '"A supplement cannot be raised on an original that is Closed or Rejected."', color="nfColor.DangerText", AccessibleLabel='"Refused"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch",
         Visible='gblParent.tsc_status = "Closed" || gblParent.tsc_status = "Rejected"'),
    cap("txtNwSupCap", "Amount of this supplement (RM)"),
    number_input("numNwSup", '"Supplement amount in RM, required"', default=f"RoundUp((Coalesce({gst}.'EAC (RM)', 0) - {fam_appr}) / 100000, 0) * 100000", AlignInContainer="AlignInContainer.Stretch", Height=TOUCH),
], gap="nfSpace.Sm", Visible=SUP, AlignInContainer="AlignInContainer.Stretch", FillPortions=0, Height=220)
why = container("cntNwWhy", "Vertical", [
    text("txtNwWhyCap", f'If({SUP}, "Why this supplement (at least 20 characters)", "Why this project (at least 20 characters)")', size="nfType.Caption", weight="Semibold", color="nfColor.TextMuted", AccessibleLabel='"Justification, at least 20 characters"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch"),
    text_input("txtNwWhy", '"What it is for and what happens without it"', '"Justification, at least 20 characters"', kind="Multiline", AlignInContainer="AlignInContainer.Stretch", Height=100, TriggerOutput="TriggerOutput.Keypress"),
    text("txtNwRoute", route, color="nfColor.InfoText", Fill="nfColor.InfoFill", AccessibleLabel=route, AutoHeight="true", PaddingTop="nfSpace.Md", PaddingBottom="nfSpace.Md",
         PaddingLeft="nfSpace.Md", PaddingRight="nfSpace.Md", AlignInContainer="AlignInContainer.Stretch"),
], gap="nfSpace.Sm", Visible=f"{SUP} || locStep = 3", AlignInContainer="AlignInContainer.Stretch", FillPortions=0, Height=240)
ROWS = ('{Code: "ENG", Name: "Engineering", Total: 0, Y1: 0, Y2: 0}, {Code: "MAT", Name: "Materials and equipment", Total: 0, Y1: 0, Y2: 0}, '
        '{Code: "FAB", Name: "Fabrication and construction", Total: 0, Y1: 0, Y2: 0}, {Code: "DRL", Name: "Drilling services", Total: 0, Y1: 0, Y2: 0}, '
        '{Code: "MAR", Name: "Marine and logistics", Total: 0, Y1: 0, Y2: 0}, {Code: "OWN", Name: "Owner\'s costs", Total: 0, Y1: 0, Y2: 0}, {Code: "CON", Name: "Contingency", Total: 0, Y1: 0, Y2: 0}')
NUM = "With({ last: First(Sort(Filter(AFEs, StartsWith('AFE no', tcPrefix)), 'AFE no', SortOrder.Descending)).'AFE no' }, tcPrefix & Text(Coalesce(Value(Right(last, 3)), 0) + 1, \"000\"))"
send = ("UpdateContext({ locBusy: true });\n"
        f"With({{ no: {NUM}, me: User() }},\n"
        f"  With({{ a: Patch({AF}, Defaults({AF}), {{ 'AFE no': no, Kind: If({SUP}, \"Supplement\", \"Original\"),\n"
        "        Title: If(" + SUP + ", \"Supplement to \" & gblParent.'AFE no' & \": \" & gblParent.Title, Trim(txtNwTitle.Text)),\n"
        "        'Asset code': If(" + SUP + ", gblParent.'Asset code', drpNwAsset.Selected.'Asset code'), 'AFE type': If(" + SUP + ", gblParent.'AFE type', drpNwType.Selected.Value),\n"
        "        'Parent AFE no': If(" + SUP + ", gblParent.'AFE no', Blank()), 'Amount (RM)': If(" + SUP + ", numNwSup.Value, Coalesce(Sum(colEst, Total), 0)),\n"
        "        tsc_status: \"Draft\", 'Requester': me.FullName, 'Requester email': me.Email, Justification: Trim(txtNwWhy.Text),\n"
        "        'Planned start': If(" + SUP + ", gblParent.'Planned start', dteNwStart.SelectedDate), 'Planned end': If(" + SUP + ", gblParent.'Planned end', dteNwEnd.SelectedDate),\n"
        "        'Raised on': Today(), 'Submitted on': Today(), Source: \"Live\" }) },\n"
        "    If(" + SUP + ",\n"
        f"      Patch({LN}, Defaults({LN}), {{ Line: no & \" CON\", 'AFE no': no, 'Element code': \"CON\", 'Estimate (RM)': numNwSup.Value }}),\n"
        f"      Collect({LN}, ForAll(Filter(colEst, Total > 0) As e, {{ Line: no & \" \" & e.Code, 'AFE no': no, 'Element code': e.Code, 'Estimate (RM)': e.Total }}));\n"
        f"      Patch({PH}, Defaults({PH}), {{ Phasing: no & \" \" & {y1}, 'AFE no': no, Year: {y1}, 'Planned (RM)': Coalesce(Sum(colEst, Y1), 0) }});\n"
        f"      Patch({PH}, Defaults({PH}), {{ Phasing: no & \" \" & {y2}, 'AFE no': no, Year: {y2}, 'Planned (RM)': Coalesce(Sum(colEst, Y2), 0) }})\n"
        "    );\n"
        f"    Set(gblSel, Patch({AF}, a, {{ tsc_status: \"Submitted\" }}));   // the Submitted row, not the Draft (E2E 24 Nov)\n"
        "    UpdateContext({ locBusy: false }); Set(gblParent, Blank());\n"
        "    Navigate(scrMine, ScreenTransition.None, { locToast: true, locToastKind: \"Success\", locToastMsg: no & \" sent to the finance controller.\" })\n"
        "  )\n)")
send = "IfError(" + send + ",\n  UpdateContext({ locBusy: false, locToast: true, locToastKind: \"Danger\", locToastMsg: \"Not sent. Check your connection and try again.\" }))"
nxt = f"If(locStep = 1, UpdateContext({{ locTried1: true }}); If({ok1}, ClearCollect(colEst, " + ROWS + f"); UpdateContext({{ locStep: 2 }})), locStep = 2, UpdateContext({{ locTried2: true }}); If({ok2}, UpdateContext({{ locStep: 3 }})))"
hint = text("txtNwErr", 'If(locStep = 1, "Fill in asset, type, a title of at least 10 characters and the dates.", "Each row\'s two years must add up to its total.")', size="nfType.Small", color="nfColor.DangerText",
            AccessibleLabel='"Check the fields above"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch",
            Visible=f"!{SUP} && ((locStep = 1 && locTried1 && !({ok1})) || (locStep = 2 && locTried2 && !({ok2})))")
can_send = f"Len(Trim(txtNwWhy.Text)) >= 20 && If({SUP}, {okS}, true)"
nav = container("cntNwNav", "Horizontal", [
    button("btnNwBack", '"Back"', "UpdateContext({ locStep: locStep - 1 })", appearance="Outline", accessible='"Previous step"', Visible=f"!{SUP} && locStep > 1", Height=TOUCH, FillPortions=GROW, Width=150),
    button("btnNwNext", '"Next"', nxt, accessible='"Next step"', Visible=f"!{SUP} && locStep < 3", Height=TOUCH, FillPortions=GROW, Width=150),
    button("btnNwSend", '"Submit"', send, accessible='"Submit the AFE"', Visible=f"{SUP} || locStep = 3", Height=TOUCH, FillPortions=GROW, Width=150,
           DisplayMode=f"If(locBusy || !({can_send}), DisplayMode.Disabled, DisplayMode.Edit)"),
], gap="nfSpace.Sm", LayoutJustifyContent="LayoutJustifyContent.End", AlignInContainer="AlignInContainer.Stretch", FillPortions=0, Height=TOUCH)
nw_main = container("cntNwMain", "Vertical", [
    container("cntNwSteps", "Horizontal", [step_pill(1, "Project"), step_pill(2, "Estimate"), step_pill(3, "Review and submit")], gap="nfSpace.Xs", Visible=f"!{SUP}",
              AlignInContainer="AlignInContainer.Stretch", FillPortions=0, Height="nfSize.RowSm"),
    supbox, step1, step2, step3, why, hint, nav, foot("txtNwFoot"),
], gap="nfSpace.Lg", pad=PAD, fill="nfColor.Surface", FillPortions=1, AlignInContainer="AlignInContainer.Stretch", LayoutOverflowY="LayoutOverflow.Scroll")   # scroll: Submit was below the fold at 639 px (E2E run 24 Nov)
scr_new = screen("scrNew", [
    container("cntNwRoot", "Vertical", [
        header("cmpNwHeader", f'If({SUP}, "Raise supplement", "New AFE")', f'If({SUP}, "Adds approval to " & gblParent.\'AFE no\', "Step " & locStep & " of 3")',
               onback=f"If(!{SUP} && locStep > 1, UpdateContext({{ locStep: locStep - 1 }}), Navigate(scrHome, ScreenTransition.None))"),
        container("cntNwBody", "Horizontal", [nw_main], gap="nfSpace.Lg", pad=PAD, FillPortions=1, AlignInContainer="AlignInContainer.Stretch", LayoutMaxWidth=1100),
    ], gap=0, fill="nfColor.Canvas", Width="Parent.Width", Height="Parent.Height", LayoutAlignItems="LayoutAlignItems.Center"),
    *toast("Nw"),
    instance("cmpNwBusy", "cmpLoadingOverlay", dict(Show="locBusy", Visible="locBusy", Message='"Sending..."', X=0, Y=0)),
], Fill="nfColor.Canvas",
    OnVisible='ClearCollect(colEst, ' + ROWS + '); UpdateContext({ locStep: 1, locTried1: false, locTried2: false, locBusy: false, locToast: false, locToastKind: "Success", locToastMsg: "" })')

# ---------------------------------------------------------------- 3 My AFEs (scrTplListDetail)
row = [container("cntMnRow", "Vertical", [
    container("cntMnRowTop", "Horizontal", [
        text("txtMnRowNo", "ThisItem.'AFE no'", weight="Semibold", AccessibleLabel="ThisItem.'AFE no'", Wrap="false", FillPortions=1, AlignInContainer="AlignInContainer.Stretch",
             OnSelect="Set(gblSel, ThisItem); UpdateContext({ locDetail: true })"),
        pill("txtMnRowPill", "ThisItem.tsc_status")], gap="nfSpace.Sm", AlignInContainer="AlignInContainer.Stretch", LayoutAlignItems="LayoutAlignItems.Center", FillPortions=0, Height=32),
    text("txtMnRowTitle", "ThisItem.Title & \" · \" & tcMoney(ThisItem.'Amount (RM)')", size="nfType.Small", color="nfColor.TextMuted", AccessibleLabel="ThisItem.Title", Wrap="false",
         AlignInContainer="AlignInContainer.Stretch", OnSelect="Set(gblSel, ThisItem); UpdateContext({ locDetail: true })"),
], gap="nfSpace.Xxs", Width="Parent.TemplateWidth", Height="Parent.TemplateHeight", PaddingLeft="nfSpace.Lg", PaddingRight="nfSpace.Lg",
    LayoutJustifyContent="LayoutJustifyContent.Center", fill="nfColor.Surface", BorderColor="nfColor.Divider", BorderThickness="nfSize.Border", LayoutOverflowY="LayoutOverflow.Hide")]
SEL_ST = f"LookUp({ST}, 'AFE no' = gblSel.'AFE no')"
timeline = (f"Concat(Sort(Filter({DC}, 'AFE no' = gblSel.'AFE no'), 'Decided on', SortOrder.Ascending), Step & \" \" & Lower(Outcome) & \" by the \" & Lower(Role) & \" on \" & Text('Decided on', \"dd/mm/yyyy\") & "
            "If(IsBlank(Comment), \"\", \": \" & Comment), Char(10))")
spend = (f"If(IsBlank({SEL_ST}), \"Spend appears after the nightly refresh once the AFE is approved.\", "
         f"\"Approved \" & tcMoney({SEL_ST}.'Approved (RM)') & \" · Actual \" & tcMoney({SEL_ST}.'Actual (RM)') & Char(10) & \"Committed \" & tcMoney({SEL_ST}.'Committed (RM)') & "
         f"\" · EAC \" & tcMoney({SEL_ST}.'EAC (RM)') & \" (\" & Text({SEL_ST}.'EAC % of approval', \"0%\") & \")\" & Char(10) & \"Headroom \" & tcMoney({SEL_ST}.'Headroom (RM)'))")
mine_list = container("cntMnList", "Vertical", [
    gallery("galMnRows", MINE, row, '"My AFEs"', template_size="76", FillPortions=1, AlignInContainer="AlignInContainer.Stretch", Visible=f"!IsEmpty({MINE})"),
    instance("cmpMnEmpty", "cmpEmptyState", dict(Heading='"No AFEs yet"', Body='"AFEs you raise appear here."', ActionText='"New AFE"', ShowAction="true",
             OnAction="Set(gblParent, Blank()); Navigate(scrNew, ScreenTransition.None)", Visible=f"IsEmpty({MINE})", AlignInContainer="AlignInContainer.Stretch")),
], gap="nfSpace.Sm", Width="If(nfIsMobile, Parent.Width, If(nfIsDesktop, 420, 300))", FillPortions="If(nfIsMobile, 1, 0)", Visible="!nfIsMobile || !locDetail", AlignInContainer="AlignInContainer.Stretch")
mine_det = container("cntMnDetail", "Vertical", [
    button("btnMnBack", '"Back to list"', "UpdateContext({ locDetail: false })", appearance="Subtle", accessible='"Back to the list"', icon="ArrowLeft", Visible="nfIsMobile", Height=TOUCH, AlignInContainer="AlignInContainer.Start"),
    text("txtMnTitle", "Coalesce(gblSel.'AFE no' & \" · \" & gblSel.Title, \"Pick an AFE\")", size="nfType.SectionHead", weight="Semibold", AccessibleLabel='"AFE"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch"),
    pill("txtMnPill", "gblSel.tsc_status", Visible="!IsBlank(gblSel)", AlignInContainer="AlignInContainer.Start"),
    text("txtMnSpend", spend, AccessibleLabel='"Spend against approval"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch", Visible="!IsBlank(gblSel)"),
    container("cntMnFlag", "Horizontal", [
        text("txtMnFlag", '"Supplement needed: EAC is more than 110% of approval."', color="nfColor.DangerText", AccessibleLabel='"Supplement needed"', FillPortions=1, AlignInContainer="AlignInContainer.Stretch"),
        button("btnMnSup", '"Raise supplement"', "Set(gblParent, gblSel); Navigate(scrNew, ScreenTransition.None)", appearance="Outline", accessible='"Raise a supplement"', Height=TOUCH, Width=180),
    ], gap="nfSpace.Sm", pad="nfSpace.Sm", fill="nfColor.DangerFill", Visible=f"Coalesce({SEL_ST}.'Supplement needed', false)", AlignInContainer="AlignInContainer.Stretch", FillPortions=0, Height=72, LayoutAlignItems="LayoutAlignItems.Center"),
    cap("txtMnTlCap", "Decisions"),
    text("txtMnTimeline", f'If(IsEmpty(Filter({DC}, \'AFE no\' = gblSel.\'AFE no\')), "Waiting for the finance controller.", {timeline})', AccessibleLabel='"Decisions"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch", Visible="!IsBlank(gblSel)"),
    text("txtMnComment", "If(IsBlank(gblSel.'Last comment'), \"\", \"Last comment: \" & gblSel.'Last comment')", color="nfColor.TextMuted", AccessibleLabel='"Last comment"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch"),
], gap="nfSpace.Md", pad="nfSpace.Lg", fill="nfColor.Surface", FillPortions=1, Visible="!nfIsMobile || locDetail", AlignInContainer="AlignInContainer.Stretch", BorderColor="nfColor.Border", BorderThickness="nfSize.Border")
scr_mine = screen("scrMine", [
    container("cntMnRoot", "Vertical", [
        header("cmpMnHeader", '"My AFEs"', 'If(nfIsMobile, "Tap an AFE to see its spend and decisions", "Your AFEs, their decisions and spend")'),
        container("cntMnBody", "Horizontal", [mine_list, mine_det], gap="nfSpace.Lg", pad=PAD, FillPortions=1, AlignInContainer="AlignInContainer.Stretch", LayoutMaxWidth="nfPageMaxW"),
        foot("txtMnFoot"),
    ], gap=0, fill="nfColor.Canvas", Width="Parent.Width", Height="Parent.Height", LayoutAlignItems="LayoutAlignItems.Center"),
    *toast("Mn"),
], Fill="nfColor.Canvas", OnVisible=f"UpdateContext({{ locDetail: !IsBlank(gblSel) }}); Refresh({AF}); Refresh({ST}); Refresh({DC})")

# ---------------------------------------------------------------- rule self-test (T16)
calc = "ForAll(tcVectors As v, { Ok: tcTier(v.A + v.P + v.R) = v.Tier, N: Text(v.A + v.P + v.R) })"
st_text = f'"LOA vectors passed: " & CountRows(Filter({calc}, Ok)) & " of " & CountRows(tcVectors)'
scr_test = screen("scrRuleTest", [container("cntRtRoot", "Vertical", [
    header("cmpRtHeader", '"LOA rule self-test"', '"tcTier against the oracle vectors"'),
    text("txtRtResult", st_text, size="nfType.SectionHead", weight="Semibold", AccessibleLabel=st_text, AutoHeight="true", AlignInContainer="AlignInContainer.Stretch", PaddingLeft="nfSpace.Xxl"),
    text("txtRtFails", f'"Failed totals: " & Concat(Filter({calc}, !Ok), N, "; ")', color="nfColor.DangerText", AccessibleLabel='"Failed vectors"', AutoHeight="true", AlignInContainer="AlignInContainer.Stretch", PaddingLeft="nfSpace.Xxl"),
], gap="nfSpace.Lg", fill="nfColor.Canvas", Width="Parent.Width", Height="Parent.Height")], Fill="nfColor.Canvas")

a = app(formulas=formulas, StartScreen='If(Param("screen") = "ruletest", scrRuleTest, scrHome)')
if os.path.isdir(OUT):
    for f in os.listdir(OUT):
        pass  # the mount cannot delete; write_app overwrites every screen file
write_app(OUT, a, [scr_home, scr_new, scr_mine, scr_test])
cdir = os.path.join(OUT, "Components"); os.makedirs(cdir, exist_ok=True)
for f in ["cmpPageHeader", "cmpKpiTile", "cmpEmptyState", "cmpToast", "cmpLoadingOverlay"]:
    shutil.copy(os.path.join(KIT, "components", "Components", f + ".pa.yaml"), os.path.join(cdir, f + ".pa.yaml"))
print("wrote", sorted(os.listdir(OUT)), sorted(os.listdir(cdir)))
