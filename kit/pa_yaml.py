#!/usr/bin/env python3
"""pa_yaml.py - build canvas-app source (.pa.yaml) from Python, lint it, and run the accessibility pass.

WHY (guide §181a, §185). P32 and P33 each wrote their own `ctl()`/`blk()` helpers (gen_app.py,
gen_mark_screen.py) and their own accessibility fixer (fix_a11y.py). The second time a deliverable
recurs it becomes a component (house rule, App C). This module is that component: one builder, one
linter, one a11y pass, each with controls (test_powerapps_kit.py).

GROUND TRUTH. Control names, versions, property names and enum values come from
`_ENGINE/reference/power-platform/PA_YAML_CONTROL_CATALOG.json` - harvested from 95 Studio-saved
.pa.yaml files (powerappsui samples, saved June 2026) plus 61 PnP snippet files, never from memory.
Two forms exist and both are proven to load:
  * Studio-saved (msapp Src/):  `Control: ModernButton@1.0.0` (versioned)
  * canvas-authoring MCP sync:   `Control: Label` (unversioned; P32/P33 compiled these first time)
`versions=True` (default) writes the newest version seen in Studio-saved files; pass False to match
an MCP-synced project. FIRST COMPILE DECIDES: record the result in SETTLED.md.

BUILD
    from pa_yaml import *
    s = screen("scrHome", [container("cntRoot", "Vertical", [text("lblTitle", '"Hello"')])], Fill="nfColor.Canvas")
    write_app(out_dir, app(formulas=open("tokens.fx").read()), [s], components=[])

LINT  (exit 0 clean, 1 errors, 4 read nothing)
    python3 pa_yaml.py lint <folder or files...> [--json] [--source dataverse]
A11Y PASS (line-based, safe on MCP-synced files whose properties the server re-sorted; guide §179c)
    python3 pa_yaml.py a11y <folder> [--labels labels.json]
    python3 pa_yaml.py --selftest
"""
from __future__ import annotations

import json
import os
import re
import sys

import yaml

yaml.SafeLoader.add_constructor("tag:yaml.org,2002:value", lambda l, n: l.construct_scalar(n))

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.normpath(os.path.join(HERE, "..", "..", "reference", "power-platform", "PA_YAML_CONTROL_CATALOG.json"))

# newest version seen in a Studio-saved file (catalog, 2026-11-10). Base name -> versioned name.
VERSION = {"GroupContainer": "1.5.0", "ModernText": "1.0.0", "ModernButton": "1.0.0", "ModernTextInput": "1.1.2",
           "ModernDropdown": "1.0.3", "ModernCombobox": "1.1.1", "ModernDatePicker": "1.0.2", "ModernCheckbox": "1.0.1",
           "ModernToggle": "1.0.0", "ModernTabList": "1.0.1", "Gallery": "2.15.0", "Image": "2.2.3", "HtmlViewer": "2.1.0",
           "Label": "2.5.1", "Rectangle": "2.3.0", "Classic/Button": "2.2.0", "Classic/Icon": "2.5.0", "Timer": "2.1.0",
           "Classic/TextInput": "2.3.2", "Attachments": "2.3.0", "Spinner": "1.4.6", "Progress": "1.1.34",
           # first seen in Nov-2026 Studio saves (Power App Sample CA04-CA10, guide §185); not yet compiled by this kit
           "ModernNumberInput": "1.1.2", "ModernDataGrid": "1.7.0", "ModernDataGridColumn": "1.2.0",
           "ModernMetricCard": "1.0.0", "ModernCard": "1.3.0", "ModernCardGallery": "1.1.0", "ModernIcon": "1.1.1",
           "ModernProgressBar": "1.0.0", "ModernBadge": "1.0.0", "ModernAvatar": "1.1.0", "ModernAttachments": "1.3.0"}

INTERACTIVE_MODERN = {"ModernButton", "ModernTextInput", "ModernDropdown", "ModernCombobox", "ModernDatePicker",
                      "ModernCheckbox", "ModernToggle", "ModernTabList", "Gallery", "ModernNumberInput",
                      "ModernCardGallery", "ModernDataGrid"}   # CA12 (guide §217c): App Checker flags an unlabelled card gallery
NO_ACCESSIBLE_LABEL = {"Label", "Classic/Button"}          # guide §181b: compile error "Unknown property"
CLASSIC_FOCUSABLE = {"Label", "Rectangle"}                  # guide §181c: checker treats them as interactive
GALLERY_VARIANTS = {"Vertical", "Horizontal", "VariableHeight"}
RESERVED_FIELDS = {"empty", "true", "false", "and", "or", "not", "in", "exactin", "as", "self", "parent",
                   "thisitem", "thisrecord", "blank"}

# ============================================================================ builder
def _f(v) -> str:
    """Normalise a property value to a Power Fx formula string with a leading '='."""
    if isinstance(v, bool):
        v = "true" if v else "false"
    v = str(v).strip()
    return v if v.startswith("=") else "=" + v


def _scalar(v: str, ind: int) -> str:
    """YAML scalar for a formula. Block style when multi-line or when plain style would mis-parse
    (': ' or ' #' inside, leading quote/brace) - guide §183c."""
    needs_block = "\n" in v or ": " in v or " #" in v or v.endswith(":")   # a leading '=' keeps the rest plain-safe (Studio writes ="text" plain)
    if not needs_block:
        return v
    pad = " " * (ind + 2)
    return "|-\n" + "\n".join(pad + line if line else "" for line in v.split("\n"))


class Node(dict):
    pass


def ctl(name: str, control: str, props: dict | None = None, children: list | None = None,
        variant: str | None = None, versions: bool = True) -> Node:
    base = control.split("@")[0]
    if versions and "@" not in control and base in VERSION:
        control = f"{base}@{VERSION[base]}"
    if not versions:
        control = base
    n = Node(name=name, Control=control, Properties={k: _f(v) for k, v in (props or {}).items() if v is not None})
    if variant:
        n["Variant"] = variant
    if children:
        n["Children"] = children
    return n


def _emit_props(props: dict, ind: int) -> list:
    pad = " " * ind
    return [f"{pad}{k}: {_scalar(v, ind)}" for k, v in props.items()]


def _emit_node(n: Node, ind: int) -> list:
    p = " " * ind
    L = [f"{p}- {n['name']}:", f"{p}    Control: {n['Control']}"]
    if n.get("ComponentName"):
        L.append(f"{p}    ComponentName: {n['ComponentName']}")
    if n.get("Variant"):
        L.append(f"{p}    Variant: {n['Variant']}")
    if n["Properties"]:
        L.append(f"{p}    Properties:")
        L += _emit_props(n["Properties"], ind + 6)
    if n.get("Children"):
        L.append(f"{p}    Children:")
        for c in n["Children"]:
            L += _emit_node(c, ind + 6)
    return L


# ---- control helpers (props named as Studio names them; read the catalog before adding one) ----
def text(name, value, size="nfType.Body", color="nfColor.TextStrong", weight=None, **kw):
    """Modern Text (ModernText). AccessibleLabel is valid here (429 of 499 Studio uses set it)."""
    props = {**dict(Text=value, Size=size, Color=color, Wrap="true"), **kw}
    if weight:
        props["FontWeight"] = f"FontWeight.{weight}"
    return ctl(name, "ModernText", props)


def label(name, value, size=13, color="nfColor.TextStrong", **kw):
    """Classic Label (points, not px). Gets TabIndex 0 + FocusedBorderThickness 2 (guide §181c); never AccessibleLabel."""
    props = {**dict(Text=value, Size=size, Color=color, TabIndex=0, FocusedBorderThickness=2), **kw}
    return ctl(name, "Label", props)


def button(name, value, onselect, appearance="Primary", accessible=None, icon=None, layout=None, **kw):
    """Modern Button. Appearance: Primary | Secondary | Outline | Subtle | Transparent (catalog)."""
    props = {**dict(Text=value, OnSelect=onselect, Appearance=f"ButtonAppearance.{appearance}",
                 AccessibleLabel=accessible or value), **kw}
    if icon:
        props["Icon"] = f'"{icon}"'
    if layout:
        props["Layout"] = f"ButtonLayout.{layout}"
    return ctl(name, "ModernButton", props)


def text_input(name, placeholder, accessible, kind=None, **kw):
    """Modern TextInput. kind: Search | Multiline | Password ... (TextInputType)."""
    props = {**dict(Placeholder=placeholder, AccessibleLabel=accessible, Appearance="Appearance.Outline",
                 TriggerOutput="TriggerOutput.Delayed"), **kw}
    if kind:
        props["Type"] = f"TextInputType.{kind}"
    return ctl(name, "ModernTextInput", props)


def dropdown(name, items, display, accessible, default=None, **kw):
    props = {**dict(Items=items, ItemDisplayText=display, AccessibleLabel=accessible, Appearance="Appearance.Outline"), **kw}
    if default:
        props["Default"] = default
    return ctl(name, "ModernDropdown", props)


def combobox(name, items, display, accessible, multi=False, **kw):
    props = {**dict(Items=items, ItemDisplayText=display, AccessibleLabel=accessible, Appearance="Appearance.Outline",
                 SelectMultiple="true" if multi else "false", IsSearchable="true"), **kw}
    return ctl(name, "ModernCombobox", props)


def date_picker(name, accessible, **kw):
    props = {**dict(AccessibleLabel=accessible, Appearance="Appearance.Outline", Format="DatePickerFormat.Short",
                 StartOfWeek="StartOfWeek.Monday"), **kw}
    return ctl(name, "ModernDatePicker", props)


def toggle(name, accessible, default="false", **kw):
    return ctl(name, "ModernToggle", {**dict(AccessibleLabel=accessible, Default=default), **kw})


def number_input(name, accessible, default="0", **kw):
    """ModernNumberInput: read the value with <name>.Value (Studio-saved CA04/CA06)."""
    return ctl(name, "ModernNumberInput", {**dict(AccessibleLabel=accessible, Default=default), **kw})


def data_grid_column(name, field, display, text=None, variant="Textual", **kw):
    """One ModernDataGridColumn. field = the column's internal name; text defaults to ThisItem.<field>.
    Variants seen in Studio saves: Textual, Number, Button, Url, Image, OptionSetArray. A choice column
    shows its label with text="ThisItem.<field>.Value"."""
    props = {**dict(FieldDisplayName=f'"{display}"', FieldName=f'"{field}"', Text=text or f"ThisItem.{field}"), **kw}
    return ctl(name, "ModernDataGridColumn", props, variant=variant)


def data_grid(name, items, columns, page_size=None, searchable=False, **kw):
    """ModernDataGrid@1.7.0 as Studio saves it (CA05): Pagination.Number pages on the server; Searchable +
    DelegateSearch put a delegated search box on the grid. Read the row with <name>.Selected."""
    props = {**dict(Items=items, Pagination="Pagination.Number"), **kw}
    if page_size:
        props["PageSize"] = page_size
    if searchable:
        props.update(Searchable="true", DelegateSearch="true")
    return ctl(name, "ModernDataGrid", props, children=list(columns))


def metric_card(name, title, value, description=None, highlight=None, **kw):
    """ModernMetricCard (CA04): a KPI tile with optional left highlight bar. value is a Text formula."""
    props = dict(Title=f'"{title}"', DisplayText=value, AutoHeight="true", BorderStyle="BorderStyle.Solid",
                 BorderColor="nfColor.Border", DropShadow="DropShadow.Semibold")
    if description:
        props["Description"] = f'"{description}"'
    if highlight:
        props.update(HighlightColor=highlight, HighlightPosition="MetricCardHighlightPosition.Left")
    return ctl(name, "ModernMetricCard", {**props, **kw})


def card(name, title, subtitle=None, description=None, image=None, **kw):
    """ModernCard@1.3.0 (CA09): title/subtitle/description with an optional image."""
    props = dict(Title=title)
    for k, v in (("Subtitle", subtitle), ("Description", description), ("Image", image)):
        if v:
            props[k] = v
    if image:
        props["ImagePlacement"] = "ImagePlacement.AfterHeader"
    return ctl(name, "ModernCard", {**props, **kw})


def icon(name, icon_name, color="nfColor.TextMuted", **kw):
    """ModernIcon (Fluent icon by name, e.g. "Settings", "ArrowClockwise")."""
    return ctl(name, "ModernIcon", {**dict(Icon=f'"{icon_name}"', IconColor=color), **kw})


def html(name, html_text, **kw):
    return ctl(name, "HtmlViewer", {**dict(HtmlText=html_text), **kw})


def svg_image(name, svg_formula, accessible, **kw):
    """Image fed an SVG string: "data:image/svg+xml;utf8," & EncodeUrl(svg) (Badge component pattern)."""
    return ctl(name, "Image", {**dict(Image=f'"data:image/svg+xml;utf8," & EncodeUrl({svg_formula})',
                                   AccessibleLabel=accessible, TabIndex=-1), **kw})


def container(name, direction, children, gap="nfSpace.Md", pad=None, fill=None, **kw):
    """AutoLayout container. direction: Vertical | Horizontal. DropShadow.None (1,113 of 1,183 Studio uses)."""
    props = {**dict(LayoutDirection=f"LayoutDirection.{direction}", LayoutGap=gap, DropShadow="DropShadow.None"), **kw}
    if pad is not None:
        props.update(PaddingTop=pad, PaddingBottom=pad, PaddingLeft=pad, PaddingRight=pad)
    if fill:
        props["Fill"] = fill
    return ctl(name, "GroupContainer", props, children=children, variant="AutoLayout")


def manual(name, children, **kw):
    return ctl(name, "GroupContainer", {**dict(DropShadow="DropShadow.None"), **kw}, children=children, variant="ManualLayout")


def gallery(name, items, template_children, accessible, variant="Vertical", template_size=48, **kw):
    if variant not in GALLERY_VARIANTS:
        raise ValueError(f"Gallery variant {variant!r} - Studio accepts {sorted(GALLERY_VARIANTS)} (guide §181b)")
    props = {**dict(Items=items, TemplateSize=template_size, TemplatePadding=0, ShowScrollbar="false",
                 AccessibleLabel=accessible, TabIndex=0, LoadingSpinner="LoadingSpinner.Data"), **kw}
    return ctl(name, "Gallery", props, children=template_children, variant=variant)


def timer(name, duration, on_end=None, **kw):
    props = {**dict(Duration=duration, Visible="false"), **kw}
    if on_end:
        props["OnTimerEnd"] = on_end
    return ctl(name, "Timer", props)


# ---- containers of controls ----
def screen(name: str, children: list, **props) -> dict:
    return {"kind": "screen", "name": name, "Properties": {k: _f(v) for k, v in props.items()}, "Children": children}


def instance(name: str, component_name: str, props: dict | None = None) -> Node:
    """A component on a screen: `Control: CanvasComponent` + `ComponentName:` (DocRouter scrHome, Studio-saved)."""
    n = ctl(name, "CanvasComponent", props, versions=False)
    n["ComponentName"] = component_name
    return n


def prop_input(name, dtype, default, desc=""):
    return (name, {"PropertyKind": "Input", "DisplayName": name, "Description": desc or name, "DataType": dtype, "Default": _f(default)})


def prop_output(name, dtype, value, desc=""):
    """Output: declared without Default; its VALUE is a formula in the component's Properties (Studio-saved shape)."""
    return (name, {"PropertyKind": "Output", "DisplayName": name, "Description": desc or name, "DataType": dtype, "_value": _f(value)})


def prop_action(name, body, desc=""):
    """Behavior property the HOST calls (cmp.Name()); body lives in Properties (DocRouter cmpDetEditWorkflow.LoadDraft)."""
    return (name, {"PropertyKind": "Action", "DisplayName": name, "Description": desc or name, "ReturnType": "None", "_value": _f(body)})


def prop_event(name, desc=""):
    return (name, {"PropertyKind": "Event", "DisplayName": name, "Description": desc or name, "ReturnType": "None", "Default": "=false"})


def component(name: str, custom: list, children: list, access_app_scope=True, **props) -> dict:
    """AccessAppScope true lets the component read App.Formulas tokens (nfColor...) - DocRouter components do."""
    cust, p = {}, {}
    for pn, pd in custom:
        pd = dict(pd)
        if "_value" in pd:
            p[pn] = pd.pop("_value")
        cust[pn] = pd
    p.update({k: _f(v) for k, v in props.items()})
    return {"kind": "component", "name": name, "Custom": cust, "AccessAppScope": access_app_scope,
            "Properties": dict(sorted(p.items())), "Children": children}


def app(formulas: str | None = None, **props) -> dict:
    p = {k: _f(v) for k, v in props.items()}
    if formulas:
        p = {"Formulas": "=" + formulas.strip(), **p}
    return {"kind": "app", "Properties": p}


HEADER = "# Generated by _ENGINE/templates/powerapps/pa_yaml.py - edit the generator, not this file.\n"


def emit_screen(s: dict) -> str:
    L = ["Screens:", f"  {s['name']}:"]
    if s["Properties"]:
        L.append("    Properties:")
        L += _emit_props(s["Properties"], 6)
    if s["Children"]:
        L.append("    Children:")
        for c in s["Children"]:
            L += _emit_node(c, 6)
    return HEADER + "\n".join(L) + "\n"


def emit_component(c: dict) -> str:
    L = ["ComponentDefinitions:", f"  {c['name']}:", "    DefinitionType: CanvasComponent",
         f"    AccessAppScope: {'true' if c['AccessAppScope'] else 'false'}"]
    if c["Custom"]:
        L.append("    CustomProperties:")
        for pn, pd in c["Custom"].items():
            L.append(f"      {pn}:")
            for k, v in pd.items():
                if k == "Default":
                    L.append(f"        Default: {_scalar(v, 8)}")
                elif k == "Description":
                    L.append(f"        {k}: {json.dumps(v)}")
                else:
                    L.append(f"        {k}: {v}")
    if c["Properties"]:
        L.append("    Properties:")
        L += _emit_props(c["Properties"], 6)
    if c["Children"]:
        L.append("    Children:")
        for ch in c["Children"]:
            L += _emit_node(ch, 6)
    return HEADER + "\n".join(L) + "\n"


def emit_app(a: dict) -> str:
    L = ["App:", "  Properties:"] + _emit_props(a["Properties"], 4)
    return HEADER + "\n".join(L) + "\n"


def write_app(out_dir: str, a: dict | None, screens: list, components: list = ()) -> list:
    os.makedirs(out_dir, exist_ok=True)
    written = []
    if a:
        p = os.path.join(out_dir, "App.pa.yaml"); open(p, "w", encoding="utf-8", newline="\n").write(emit_app(a)); written.append(p)
    for s in screens:
        p = os.path.join(out_dir, f"{s['name']}.pa.yaml"); open(p, "w", encoding="utf-8", newline="\n").write(emit_screen(s)); written.append(p)
    if components:
        cd = os.path.join(out_dir, "Components"); os.makedirs(cd, exist_ok=True)
        for c in components:
            p = os.path.join(cd, f"{c['name']}.pa.yaml"); open(p, "w", encoding="utf-8", newline="\n").write(emit_component(c)); written.append(p)
    return written


# ============================================================================ lint
def _load_catalog():
    try:
        return json.load(open(CATALOG, encoding="utf-8"))["controls"]
    except Exception:
        return None


def _walk(children, out, file, parent=None):
    for ch in children or []:
        if not isinstance(ch, dict):
            continue
        for name, node in ch.items():
            if isinstance(node, dict):
                out.append((file, name, node, parent))
                _walk(node.get("Children"), out, file, name)


# ---- delegation scan (guide §192) ------------------------------------------------------------------------------------
# Positive set: CA11's own AppCheckerResult.sarif (88 hints at 26 properties). Kinds map to App Checker's causes:
# aggregate = OpNotSupportedByService(CountRows/CountIf/...), not-equal = OpNotSupportedByColumn (`<>` on a column),
# not = OpNotSupportedByService(Not), in = InOpRhs; shaping/search/column-fn carry v1's checks forward.
DELEG_WHY = {
    "aggregate": "CountRows/CountIf/Sum/Average/Min/Max over the list answer from the first 500/2,000 rows only: keep a metrics row or wrap a named formula in FirstN (POWERFX §4)",
    "not-equal": "`<>` in a Filter/LookUp predicate does not delegate: OR the allowed equalities instead (POWERFX §4.3)",
    "not": "Not()/! in a predicate does not delegate: test the positive condition",
    "in": "`in` (text contains / membership) does not delegate: use StartsWith or a delegable search control",
    "column-fn": "a function applied to a COLUMN in a predicate (Lower, Trim, Text, ...) does not delegate",
    "shaping": "Distinct/AddColumns/GroupBy/ShowColumns over the list run locally on the first 500/2,000 rows",
    "search": "Search() does not delegate on SharePoint: use a Filter with StartsWith",
    "named": "reads a named formula that is itself not delegable (App Checker reports every reader too; fix the formula)",
}
_DELEG_AGG = {"CountRows", "CountIf", "Sum", "Average", "Min", "Max", "StdevP", "VarP"}
_DELEG_PRED = {"Filter", "LookUp", "CountIf", "Search"}
_DELEG_SHAPE = {"Distinct", "AddColumns", "GroupBy", "ShowColumns", "DropColumns", "RenameColumns"}
_DELEG_PASS = {"Filter", "Sort", "SortByColumns", "Search", "AddColumns", "DropColumns", "ShowColumns", "RenameColumns",
               "Distinct"}
_DELEG_SCALAR_OK = {"Sum", "Average", "Min", "Max", "StdevP", "VarP"}   # also take plain numbers: Max(Reorder, 1)
_TABLE_USE = {"Filter", "LookUp", "Search", "CountRows", "CountIf", "Sort", "SortByColumns", "Distinct", "AddColumns",
              "GroupBy", "ShowColumns", "DropColumns", "RenameColumns", "Refresh", "Patch", "Defaults", "Remove",
              "RemoveIf", "UpdateIf", "First", "Last", "FirstN", "LastN", "ForAll"}
_DELEG_BUILTIN = {"ThisItem", "ThisRecord", "Self", "Parent", "App", "Host", "User", "true", "false", "Blank"}
_COL_FN = re.compile(r"\b(Lower|Upper|Trim|Len|Left|Right|Mid|Text|Value|Year|Month|Day|DateValue|Coalesce)\s*\(\s*"
                     r"([A-Za-z_][A-Za-z0-9_]*(?:\.Value)?)\s*[,)]")


def _mask_strings(s):
    """Blank "..." literals (a doubled quote toggles twice, so escapes are safe) AND // and /* */ comments, so no
    structure is read from text. 2026-11-12: the kit's own list template explains "`in` and `<>` do not delegate" in
    a // comment inside its Filter, and v2 without comment masking flagged it (guide §192c)."""
    out, i, n, q = [], 0, len(s), False
    while i < n:
        c = s[i]
        if q:
            out.append(c if c == '"' else " ")
            q = c != '"'
            i += 1
        elif c == '"':
            q = True
            out.append(c)
            i += 1
        elif s.startswith("//", i):
            j = s.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in s[i:j]))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _fx_calls(s):
    """Every call `Name(args)` in a (masked) formula: [(name, [args], start, end)], brackets balanced, nested included."""
    out = []
    for m in re.finditer(r"\b([A-Z][A-Za-z]*)\s*\(", s):
        i, depth, args, cur, q = m.end(), 1, [], [], None
        while i < len(s) and depth:
            c = s[i]
            if q:
                cur.append(c)
                q = None if c == q else q
            elif c in "'\"":
                q = c
                cur.append(c)
            elif c in "([{":
                depth += 1
                cur.append(c)
            elif c in ")]}":
                depth -= 1
                if depth:
                    cur.append(c)
            elif c == "," and depth == 1:
                args.append("".join(cur))
                cur = []
            else:
                cur.append(c)
            i += 1
        args.append("".join(cur))
        out.append((m.group(1), [a.strip() for a in args], m.start(), i))
    return out


def _root(expr, depth=0):
    """The identifier a table expression starts from, through Filter/Sort/AddColumns/... ; None for literals/other calls."""
    e = re.sub(r"\s+As\s+[A-Za-z_][A-Za-z0-9_]*\s*$", "", (expr or "").strip())
    m = re.match(r"([A-Z][A-Za-z]*)\s*\(", e)
    if m:
        calls = _fx_calls(e)
        if depth < 8 and calls and calls[0][2] == 0 and calls[0][0] in _DELEG_PASS and calls[0][1]:
            return _root(calls[0][1][0], depth + 1)
        return None
    g = re.fullmatch(r"\[@\s*('[^']+'|[A-Za-z_][A-Za-z0-9_]*)\s*\]", e)   # [@Name]: the global disambiguation
    if g:                                       # operator Studio writes in generated apps (CA12, guide §217a)
        return g.group(1)
    return e if re.fullmatch(r"'[^']+'|[A-Za-z_][A-Za-z0-9_]*", e) else None


def _record_fields(rec):
    """Top-level field names of a record literal `{a: ..., b: {c: 1}}` -> {'a', 'b'}. v2's [^{}]* regex stopped at the
    first nested record and missed FA01's `_approvalConfig` (a With field holding ForAll records; guide §192d)."""
    rec = rec.strip()
    if not rec.startswith("{"):
        return set()
    out, depth, start = set(), 0, 1
    for i, c in enumerate(rec):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if depth == 1 and c in "{,":
            m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*|'[^']+')\s*:", rec[i + 1:])
            if m:
                out.add(m.group(1))
    return out


def _deleg_context(formulas_by_file, control_names):
    """What is NOT a data source: collections, variables, controls, With fields, named formulas wrapped in FirstN."""
    local, named, tables = set(_DELEG_BUILTIN) | set(control_names), {}, set()
    for _, where, v in formulas_by_file:
        for name, args, _, _ in _fx_calls(_mask_strings(v)):   # what the app USES as a table anywhere
            if name in _TABLE_USE and args and _root(args[0]):
                tables.add(_root(args[0]))
            if name == "Choices" and args:
                tables.add(re.sub(r"^\[@\s*(.*?)\s*\]$", r"\1", args[0].split(".")[0].strip()))   # [@'List'].Col (CA12)
        local |= set(re.findall(r"\b(?:ClearCollect|Collect)\(\s*([A-Za-z_][A-Za-z0-9_]*)", v))
        local |= set(re.findall(r"\bSet\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,", v))
        for name, args, _, _ in _fx_calls(_mask_strings(v)):   # With/UpdateContext record fields, nested {} included
            if name in ("With", "UpdateContext") and args:
                local |= _record_fields(args[0])
        local |= set(re.findall(r"\bAs\s+([A-Za-z_][A-Za-z0-9_]*)", v))
        if where.endswith(".Formulas"):
            named.update(_named_formulas(v))
    return {"local": local, "named": named, "tables": tables}


def _named_formulas(v):
    """{name: expression} from an App.Formulas block. Comments and string contents are masked FIRST: Studio-saved
    apps put // blocks between definitions, and v2's first parser read none of CA06's names (guide §192d).
    UDF definitions `Name(args): Type = ...` are skipped (they take parameters; not a table)."""
    m = _mask_strings(str(v)).lstrip().lstrip("=")
    return {nm: ex.strip() for nm, ex in
            re.findall(r"(?:^|;)\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)\s*(.*?)(?=;|$)", m, re.S)}


def _is_source(name, ctx, seen=()):
    if not name or name in ctx["local"] or name in seen:
        return False
    ex = ctx["named"].get(name)
    if ex is not None:   # a named formula: local when wrapped in FirstN (POWERFX §4.7), else whatever it reads
        return "FirstN(" not in ex and _is_source(_root(ex), ctx, seen + (name,))
    return True


def delegation_kinds(formula, ctx):
    """Kinds of non-delegable use in one formula (sorted, unique). Pure: the selftest calls it directly."""
    s = _mask_strings(str(formula))
    kinds = set()
    for name, args, _, _ in _fx_calls(s):
        if not args or not _is_source(_root(args[0]), ctx):
            continue
        if name in _DELEG_AGG and ctx.get("source") != "dataverse" and (name not in _DELEG_SCALAR_OK or _root(args[0]) in ctx.get("tables", ())
                                   or args[0].lstrip().startswith(tuple(_DELEG_PASS))):
            kinds.add("aggregate")   # Sum/Min/Max/... only when the argument is used as a TABLE somewhere (§192d)
        if name in _DELEG_SHAPE:
            kinds.add("shaping")
        if name == "Search":
            kinds.add("search")
        if name in _DELEG_PRED:
            for pred in args[1:] if name != "Search" else []:
                if "<>" in pred:
                    kinds.add("not-equal")
                if re.search(r"(?:^|[^A-Za-z0-9_])(?:Not\s*\(|!(?!=))", pred):
                    kinds.add("not")
                if re.search(r"\s(?:in|exactin)\s", pred):
                    kinds.add("in")
                for m in _COL_FN.finditer(pred):
                    if m.group(2).split(".")[0] not in ctx["local"]:
                        kinds.add("column-fn")
    return sorted(kinds)


def lint(paths: list, catalog=None, source=None) -> dict:
    files = []
    for p in paths:
        if os.path.isdir(p):
            for dp, _, fn in os.walk(p):
                files += [os.path.join(dp, f) for f in fn if f.endswith(".pa.yaml") and not f.startswith("_EditorState")]
        elif os.path.isfile(p):
            files.append(p)
    res = {"files_read": 0, "controls_read": 0, "findings": []}
    def F(sev, rule, file, where, msg):
        res["findings"].append({"severity": sev, "rule": rule, "file": os.path.basename(file), "where": where, "message": msg})
    names = {}
    screens_set, comps_set = set(), set()   # W3 Q6: the speed rules need to know which root is a screen
    has_tokens = False
    nodes = []
    formulas_by_file = []
    for f in sorted(files):
        txt = open(f, encoding="utf-8-sig").read()
        try:
            doc = yaml.safe_load(txt)
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            F("error", "YAML_PARSE", f, f"line {mark.line + 1}" if mark else "?", str(e).split("\n")[0]); continue
        res["files_read"] += 1
        if not isinstance(doc, dict):
            if isinstance(doc, list):
                _walk(doc, nodes, f)
            continue
        if "App" in doc:
            fx = str((doc["App"].get("Properties") or {}).get("Formulas", ""))
            has_tokens = has_tokens or "nfColor" in fx
            formulas_by_file.append((f, "App.Formulas", fx))
            for k, v in (doc["App"].get("Properties") or {}).items():   # OnStart etc. (guide §192d: v2 read only Formulas)
                if k != "Formulas":
                    formulas_by_file.append((f, f"App.{k}", str(v)))
        for sn, s in (doc.get("Screens") or {}).items():
            names.setdefault(sn, []).append(f)
            screens_set.add(sn)
            for k, v in (s.get("Properties") or {}).items():
                formulas_by_file.append((f, f"{sn}.{k}", str(v)))
                if not str(v).startswith("="):
                    F("error", "PROP_NOT_FORMULA", f, f"{sn}.{k}", "every property value starts with '='")
            _walk(s.get("Children"), nodes, f, sn)
        for cn, c in (doc.get("ComponentDefinitions") or {}).items():
            names.setdefault(cn, []).append(f)
            comps_set.add(cn)
            for pn, pd in (c.get("CustomProperties") or {}).items():
                if pd.get("PropertyKind") not in ("Input", "Output", "Event", "Action", "InputFunction", "OutputFunction"):   # *Function kinds: enhanced component properties (PnP multi-level-menu, FP control 2026-11-10)
                    F("error", "COMPONENT_PROP_KIND", f, f"{cn}.{pn}", f"PropertyKind {pd.get('PropertyKind')!r}")
                if pd.get("PropertyKind") == "Event" and (pd.get("Default") is None or str(pd.get("Default")).strip() in ("", "=")):
                    # 2026-11-10: powerappsui shipped 52 of these (5 apps); Studio rejects pasted YAML with PA2231. Every
                    # Microsoft sample in the library fills it (=false or =""), and none omits it (90 files read). Guide §185o.
                    F("error", "EVENT_EMPTY_DEFAULT", f, f"{cn}.{pn}", "Event property with an empty Default: pasting this YAML into Studio fails with PA2231; give it =false (a packaged .msapp still imports, guide §185o)")
            if "Visible" in (c.get("Properties") or {}):
                # P36 probe P3 (2026-11-22, guide §228a): Studio refuses Visible on a component definition;
                # set Visible on each instance instead
                F("error", "COMPONENT_DEF_VISIBLE", f, f"{cn}.Visible", "Visible is not a property of a component definition (compile error): set it on the instance (guide §228a)")
            _walk(c.get("Children"), nodes, f, cn)
    node_by = {nm: (nd, par) for _f0, nm, nd, par in nodes}
    for f, name, node, parent in nodes:
        res["controls_read"] += 1
        names.setdefault(name, []).append(f)
        control = str(node.get("Control", ""))
        base = control.split("@")[0]
        props = node.get("Properties") or {}
        where = name
        for k, v in props.items():
            v = str(v)
            formulas_by_file.append((f, f"{name}.{k}", v))
            if not v.startswith("="):
                F("error", "PROP_NOT_FORMULA", f, f"{name}.{k}", "every property value starts with '='")
            if has_tokens and re.search(r"\bRGBA\s*\(", v) and k not in ("Formulas",):
                F("info", "HARDCODED_COLOR", f, f"{name}.{k}", "app defines nfColor tokens: read nfColor.<Key> instead of an RGBA literal")
        # P36 (2026-11-22/23, guide §228a-b): three shapes Studio refuses or renders wrong, found in compile and play mode
        if base == "CanvasComponent":
            up, seen_up = parent, 0
            while up in node_by and seen_up < 50:
                if str(node_by[up][0].get("Control", "")).split("@")[0] == "Gallery":
                    F("error", "COMPONENT_IN_GALLERY", f, where, f"component instance inside gallery {up} (compile error): use plain controls in the template (guide §228a)")
                    break
                up, seen_up = node_by[up][1], seen_up + 1
        if base in ("ModernDropdown", "ModernCombobox") and re.fullmatch(r'=\s*("[^"]*"|-?\d+(\.\d+)?)\s*', str(props.get("Default", "")).strip()):
            F("error", "DROPDOWN_DEFAULT_LITERAL", f, f"{name}.Default", "Default must be a record from Items (e.g. =First(Self.Items) or ={Value: 30}), not a text or number (compile error, guide §228a)")
        if base == "ModernText" and parent in node_by and str(node_by[parent][0].get("Control", "")).split("@")[0] == "GroupContainer" \
                and node_by[parent][0].get("Variant") == "AutoLayout":
            hm = re.fullmatch(r"=\s*(\d+)\s*", str(props.get("Height", "")).strip())
            if hm and int(hm.group(1)) < 32:
                h = int(hm.group(1))
                mm = re.fullmatch(r"=\s*(\d+)\s*", str(props.get("LayoutMinHeight", "")).strip())
                pt = re.fullmatch(r"=\s*0\s*", str(props.get("PaddingTop", "")).strip()) and re.fullmatch(r"=\s*0\s*", str(props.get("PaddingBottom", "")).strip())
                if not (mm and int(mm.group(1)) <= h) or not pt:
                    F("warn", "MODERNTEXT_UNDER_MIN_HEIGHT", f, where, f"ModernText {h} px tall in an auto-layout container keeps padding 5 and LayoutMinHeight 32: it shows scroll arrows in play mode (the preview hides it). Set PaddingTop/Bottom =0 and LayoutMinHeight ={h} (guide §228b)")
        if base == "Gallery" and node.get("Variant") and node["Variant"] not in GALLERY_VARIANTS and not str(node["Variant"]).startswith("BrowseLayout_"):
            F("error", "GALLERY_VARIANT", f, where, f"Variant {node['Variant']!r}; Studio accepts Vertical/Horizontal/VariableHeight (guide §181b)")
        if base in NO_ACCESSIBLE_LABEL and "AccessibleLabel" in props:
            F("error", "ACCESSIBLE_LABEL_UNKNOWN", f, where, f"{base} has no AccessibleLabel property (compile error, guide §181b)")
        if base in CLASSIC_FOCUSABLE and ("TabIndex" not in props or "FocusedBorderThickness" not in props):
            F("warn", "A11Y_CLASSIC_FOCUS", f, where, "accessibility checker flags Label/Rectangle without TabIndex + FocusedBorderThickness (guide §181c); run `pa_yaml.py a11y`")
        if base == "Rectangle" and "AccessibleLabel" not in props:
            F("warn", "A11Y_RECT_LABEL", f, where, "Rectangle needs an AccessibleLabel (guide §181c)")
        if base in INTERACTIVE_MODERN and "AccessibleLabel" not in props:
            F("warn", "A11Y_NO_LABEL", f, where, f"{base} without AccessibleLabel")
        if base == "Image" and "OnSelect" in props and "AccessibleLabel" not in props:
            F("warn", "A11Y_NO_LABEL", f, where, "clickable Image without AccessibleLabel")
        if catalog is not None and base and control and base != "CanvasComponent":
            known = {k.split("@")[0] for k in catalog}
            if base not in known and base != "CanvasComponent" and not base[0].islower():
                pass  # component instances use their component name as Control; not a finding
            elif base in known:
                seen = set()
                for k, v in catalog.items():
                    if k.split("@")[0] == base:
                        seen |= set(v["props"])
                for k in props:
                    if k not in seen:
                        F("info", "PROP_NOT_IN_CATALOG", f, f"{name}.{k}", f"{base}.{k} never seen in a Studio-saved file; confirm with describe_control")
    for n, fs in names.items():
        if len(fs) > 1:
            F("error", "DUP_NAME", fs[0], n, f"name used {len(fs)} times (control names are app-wide)")
    for f, where, v in formulas_by_file:
        for m in re.finditer(r"With\s*\(\s*\{([^}]*)\}", v, re.S):
            for fld in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", m.group(1)):
                if fld.lower() in RESERVED_FIELDS:
                    F("error", "RESERVED_WITH_FIELD", f, where, f"With field {fld!r} is a reserved word (guide §184c: 12 parse errors, no line number)")
        if re.search(r'Coalesce\([^()]*,\s*""\s*\)\s*(=|<>)\s*""', v):
            F("error", "COALESCE_EMPTY_COMPARE", f, where, 'Coalesce(x, "") is Blank when x is blank, and Blank() = "" is false: use IsBlank(x) or "" & x (guide §184b)')
        if re.search(r"\bSum\s*\(", v) and "Coalesce" not in v and where.endswith(".Text"):
            F("warn", "SUM_MAY_BLANK", f, where, "Sum over an empty filter renders blank: wrap in Coalesce(Sum(...), 0) (guide §181e)")
    # DELEGATION_SMELL v2 (guide §192): every property, a bracket-aware scan, and only when the table traces back to
    # something that can be a DATA SOURCE (not a collection, variable, control, With field or FirstN-wrapped named formula).
    dctx = _deleg_context(formulas_by_file, names)
    dctx["source"] = source   # 'dataverse' = the tables are Dataverse; aggregates over them delegate (guide §201)
    bad_named = {nm for nm, ex in dctx["named"].items() if delegation_kinds(ex, dctx)}
    for f, where, v in formulas_by_file:
        if where.endswith(".Formulas"):
            # each named formula on its own (its own predicates), reported as App.Formulas:<Name>; where it is USED,
            # it counts as a source unless wrapped in FirstN (POWERFX §4.2, §4.7)
            for nm, ex in _named_formulas(v).items():
                for kind in delegation_kinds(ex, dctx):
                    F("warn", "DELEGATION_SMELL", f, f"App.Formulas:{nm}",
                      f"[{kind}] {DELEG_WHY[kind]} (if the source is a SharePoint list)")
            continue
        kinds = set(delegation_kinds(v, dctx))
        mv = _mask_strings(v)
        if any(re.search(r"\b" + re.escape(nm) + r"\b", mv) for nm in bad_named):
            kinds.add("named")
        for kind in sorted(kinds):
            F("warn", "DELEGATION_SMELL", f, where, f"[{kind}] {DELEG_WHY[kind]} (if the source is a SharePoint list)")
    # SELECT_QUEUED_READ (guide §188c): Select() only QUEUES the target's OnSelect; it runs after the calling formula
    # ends. A formula that Selects a button and then reads a variable that button's OnSelect sets reads the OLD value.
    # P33 S8: Save and Finalise wrote a stale record of the screen (Marked by lost) this way.
    onselect = {w.rsplit(".", 1)[0]: (ff, v) for ff, w, v in formulas_by_file if w.endswith(".OnSelect")}
    for f, where, v in formulas_by_file:
        for m in re.finditer(r"\bSelect\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)", v):
            tgt = onselect.get(m.group(1))
            if not tgt:
                continue
            sets = set(re.findall(r"\bSet\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,", tgt[1]))
            tail = v[m.end():]
            read = sorted(x for x in sets if re.search(r"\b" + re.escape(x) + r"\b", tail))
            if read:
                F("error", "SELECT_QUEUED_READ", f, where, f"Select({m.group(1)}) is queued and runs after this formula, so {', '.join(read)} still hold the old value here; build the value inline (guide §188c)")
    # ---- APP SPEED (W3 Q6, guide §211b): five warn rules, each with a negative and a false-positive control ----------
    # Sources: Learn "Code optimization" (cross-screen references load the other screen; DelayOutput), Learn modern Text
    # input (TriggerOutput defaults to Keypress since the 2026 control update), Learn "Optimize canvas app performance"
    # (Concurrent, named formulas over App.OnStart, ShowColumns), and App Checker's own app-CrossScreenEventDependencies
    # (5 hits in the CA08 and FA01 sarif files of the sample library).
    _speed_rules(res, F, nodes, formulas_by_file, dctx, screens_set)
    return res


_LOAD_COLLECT = {"ClearCollect", "Collect"}
_LOAD_READ = {"LookUp", "First", "Filter", "Search", "CountRows", "Sort", "SortByColumns"}
SPEED_WHY = {
    "ONSTART_HEAVY": "App.OnStart runs {n} data loads before the first screen draws: move them to named formulas in App.Formulas (loaded when first used) or to the OnVisible of the screen that needs them",
    "LOAD_NOT_CONCURRENT": "{n} independent loads run one after the other: wrap them in Concurrent(...) so they run in parallel",
    "SEARCH_NO_DELAY": "{inp} feeds a data-source Filter/Search on every keystroke: set {fix}",
    "CROSS_SCREEN_REF": "reads {refs} on another screen, which forces that screen to load: pass the value in a variable, a collection or Navigate's context record",
    "WIDE_COLUMN_READ": "copies every column of {src} into {col}: wrap the source in ShowColumns(...) with the columns the app uses (SharePoint; on Dataverse explicit column selection may already trim)",
}


def _speed_rules(res, F, nodes, formulas_by_file, dctx, screens_set):
    """W3 Q6. Pure over what lint() already collected; adds findings through F. Severity warn: a speed smell, not a
    compile error."""
    def src_of(name, args):
        if name in _LOAD_COLLECT:
            return args[1] if len(args) >= 2 else None
        return args[0] if args else None
    # 1 ONSTART_HEAVY: three or more data loads in App.OnStart
    for f, where, v in formulas_by_file:
        if where != "App.OnStart":
            continue
        mv, n = _mask_strings(v), 0
        for name, args, _, _ in _fx_calls(mv):
            if name in _LOAD_COLLECT | {"Refresh"} and _is_source(_root(src_of(name, args) or ""), dctx):
                n += 1
            elif name == "Set" and len(args) >= 2:
                lead = _fx_calls(args[1].strip())
                if lead and lead[0][2] == 0 and lead[0][0] in _LOAD_READ and lead[0][1] and _is_source(_root(lead[0][1][0]), dctx):
                    n += 1
        if n >= 3:
            F("warn", "ONSTART_HEAVY", f, where, SPEED_WHY["ONSTART_HEAVY"].format(n=n))
    # 2 LOAD_NOT_CONCURRENT: two or more independent ClearCollect/Collect loads in one behaviour formula, outside Concurrent
    for f, where, v in formulas_by_file:
        if not where.rsplit(".", 1)[-1].startswith("On"):
            continue
        mv = _mask_strings(v)
        calls = _fx_calls(mv)
        conc = [(s, e) for name, _, s, e in calls if name == "Concurrent"]
        indep = []
        for name, args, s, _ in calls:
            if name not in _LOAD_COLLECT or len(args) < 2 or any(a < s < b for a, b in conc):
                continue
            if not _is_source(_root(args[1]), dctx):
                continue
            if any(re.search(r"\b" + re.escape(c) + r"\b", args[1]) for c, _ in indep):
                continue   # reads an earlier load: dependent, must stay sequential
            indep.append((args[0].strip(), args[1]))
        if len(indep) >= 2:
            F("warn", "LOAD_NOT_CONCURRENT", f, where, SPEED_WHY["LOAD_NOT_CONCURRENT"].format(n=len(indep)))
    # 3 SEARCH_NO_DELAY: an undelayed text input read inside a Filter/Search/LookUp over a DATA SOURCE in an Items formula
    inputs = {}
    for f, nm, node, _ in nodes:
        base, p = str(node.get("Control", "")).split("@")[0], node.get("Properties") or {}
        if base in ("ModernTextInput", "TextInput"):
            if not any(x in str(p.get("TriggerOutput", "")) for x in ("Delayed", "FocusOut")):
                inputs[nm] = (f, "TriggerOutput: =TriggerOutput.Delayed (the modern default is Keypress)")
        elif base == "Classic/TextInput":
            if str(p.get("DelayOutput", "")).strip().lower() != "=true":
                inputs[nm] = (f, "DelayOutput: =true (the classic default is false)")
    flagged = set()
    for f, where, v in formulas_by_file:
        if not where.endswith(".Items"):
            continue
        for name, args, _, _ in _fx_calls(_mask_strings(v)):
            if name in ("Filter", "Search", "LookUp") and args and _is_source(_root(args[0]), dctx):
                body = ",".join(args[1:])
                for inp in inputs:
                    tok = ("'" + inp + "'") if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", inp) else inp
                    if inp not in flagged and re.search(r"(?<![A-Za-z0-9_.])" + re.escape(tok) + r"\.(?:Text|Value)\b", body):
                        flagged.add(inp)
                        F("warn", "SEARCH_NO_DELAY", inputs[inp][0], inp, SPEED_WHY["SEARCH_NO_DELAY"].format(inp=inp, fix=inputs[inp][1]))
    # 4 CROSS_SCREEN_REF: a formula on screen A names a control that lives on screen B (B is not App.StartScreen)
    parent = {nm: par for _, nm, _, par in nodes}
    def root_of(nm):
        for _ in range(64):
            if parent.get(nm) is None:
                return nm
            nm = parent[nm]
        return nm
    ctl_screen = {nm: root_of(nm) for nm in parent}
    ctl_screen = {nm: s for nm, s in ctl_screen.items() if s in screens_set and nm not in screens_set}
    start = next((v.strip().lstrip("=").strip().strip("'") for _, w, v in formulas_by_file if w == "App.StartScreen"), None)
    for f, where, v in formulas_by_file:
        owner = where.rsplit(".", 1)[0]
        here = owner if owner in screens_set else ctl_screen.get(owner)
        if here is None:
            continue
        refs = set()
        for q, bare in re.findall(r"'([^']+)'|(?<![A-Za-z0-9_.'])([A-Za-z_][A-Za-z0-9_]*)\b(?!\s*:)", _mask_strings(v)):
            c = q or bare
            s = ctl_screen.get(c)
            if s and s != here and s != start:
                refs.add(c)
        if refs:
            F("warn", "CROSS_SCREEN_REF", f, where, SPEED_WHY["CROSS_SCREEN_REF"].format(refs=", ".join(sorted(refs)[:3]) + (" ..." if len(refs) > 3 else "")))
    # 5 WIDE_COLUMN_READ: ClearCollect/Collect straight from a data source with no ShowColumns/DropColumns
    for f, where, v in formulas_by_file:
        for name, args, _, _ in _fx_calls(_mask_strings(v)):
            if name in _LOAD_COLLECT and len(args) >= 2 and _is_source(_root(args[1]), dctx) \
                    and not re.search(r"\b(?:ShowColumns|DropColumns)\s*\(", args[1]):
                F("warn", "WIDE_COLUMN_READ", f, where, SPEED_WHY["WIDE_COLUMN_READ"].format(src=_root(args[1]), col=args[0].strip()))


def lint_cli(argv):
    as_json = "--json" in argv
    source = argv[argv.index("--source") + 1] if "--source" in argv and argv.index("--source") + 1 < len(argv) else None
    paths = [a for i, a in enumerate(argv) if not a.startswith("--") and not (i and argv[i - 1] == "--source")]
    r = lint(paths, _load_catalog(), source)
    errs = sum(1 for x in r["findings"] if x["severity"] == "error")
    warns = sum(1 for x in r["findings"] if x["severity"] == "warn")
    if as_json:
        print(json.dumps(r, indent=1))
    else:
        for x in r["findings"]:
            print(f"  {x['severity'].upper():5s} {x['rule']:26s} {x['file']}:{x['where']}  {x['message']}")
    print(f"[scan] {r['files_read']} file(s), {r['controls_read']} control(s) read; {errs} error(s), {warns} warning(s)",
          file=sys.stderr if as_json else sys.stdout)
    if r["files_read"] == 0:
        return 4
    return 1 if errs else 0


# ============================================================================ a11y pass (line-based)
def _humanize(name: str) -> str:
    s = re.sub(r"^(lbl|btn|txt|ddl|dd|drp|cmb|dtp|tgl|chk|gal|img|rec|rct|cnt|ico|htm)", "", name)
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s).strip()
    return s[:1].upper() + s[1:] if s else name


def a11y_pass(folder: str, labels: dict | None = None) -> int:
    """Generalised from P33 fix_a11y.py. Idempotent. Adds TabIndex 0 + FocusedBorderThickness 2 to Label/Rectangle,
    TabIndex 0 to Gallery, AccessibleLabel to Rectangle and every interactive modern control that lacks one
    (from --labels, else the humanised control name)."""
    labels = labels or {}
    added = 0
    files = [os.path.join(dp, f) for dp, _, fn in os.walk(folder) for f in fn
             if f.endswith(".pa.yaml") and not f.startswith("_") and f != "App.pa.yaml"]
    for path in files:
        lines = open(path, encoding="utf-8").read().split("\n"); out = []; i = 0
        while i < len(lines):
            out.append(lines[i])
            m = re.match(r"^(\s*)- (\w+):$", lines[i])
            if m and i + 1 < len(lines) and lines[i + 1].strip().startswith("Control:"):
                name = m.group(2); base = lines[i + 1].strip().replace("Control: ", "").split("@")[0]
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith(("Properties:", "Children:")) and \
                        not re.match(r"^(\s*)- (\w+):$", lines[j]):
                    j += 1
                if j < len(lines) and lines[j].strip() == "Properties:":
                    ind = re.match(r"^(\s*)", lines[j]).group(1) + "  "
                    k = j + 1
                    while k < len(lines) and (lines[k].startswith(ind) or lines[k].strip() == ""):
                        k += 1
                    body = "\n".join(lines[j + 1:k])
                    add = []
                    if base in CLASSIC_FOCUSABLE | {"Gallery"} and not re.search(r"^\s*TabIndex:", body, re.M):
                        add.append("TabIndex: =0")
                    if base in CLASSIC_FOCUSABLE and not re.search(r"^\s*FocusedBorderThickness:", body, re.M):
                        add.append("FocusedBorderThickness: =2")
                    wants_label = base == "Rectangle" or base in INTERACTIVE_MODERN
                    if wants_label and base not in NO_ACCESSIBLE_LABEL and not re.search(r"^\s*AccessibleLabel:", body, re.M):
                        add.append(f"AccessibleLabel: ={json.dumps(labels.get(name, _humanize(name)))}")
                    if add:
                        out += lines[i + 1:j + 1] + [ind + a for a in add]; added += len(add); i = j + 1; continue
            i += 1
        open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print(f"[scan] {len(files)} screen/component file(s) read; {added} accessibility propert(ies) added")
    return 4 if not files else 0


# ============================================================================ selftest
def selftest() -> int:
    import tempfile
    fails = 0
    def check(c, m):
        nonlocal fails
        print(("  ok   " if c else "  FAIL ") + m); fails += 0 if c else 1
    d = tempfile.mkdtemp()
    s = screen("scrA", [container("cntA", "Vertical", [
        text("txtTitle", '"Leave balance"', weight="Semibold"),
        button("btnGo", '"Go"', "Navigate(scrA)"),
        label("lblNote", '"Note: see policy"'),
        ctl("rctBand", "Rectangle", {"Fill": "nfColor.Primary", "Height": 4}),
    ])], Fill="nfColor.Canvas", OnVisible='Set(varX, 1);\nSet(varY, "a: b")')
    a = app(formulas="nfColor = {Primary: RGBA(1,2,3,1)};")
    write_app(d, a, [s])
    r = lint([d], _load_catalog())
    rules = [x["rule"] for x in r["findings"]]
    check(r["files_read"] == 2 and r["controls_read"] == 5, f"positive: reads 2 files / 5 controls ({r['files_read']}/{r['controls_read']})")
    check("YAML_PARSE" not in rules and "PROP_NOT_FORMULA" not in rules, "positive: generated YAML parses; every value is a formula")
    check(rules.count("A11Y_RECT_LABEL") == 1, "positive: the one unlabelled Rectangle is flagged")
    a11y_pass(d)
    r2 = lint([d], None)
    check("A11Y_RECT_LABEL" not in [x["rule"] for x in r2["findings"]], "a11y pass fixes the Rectangle")
    before = open(os.path.join(d, "scrA.pa.yaml")).read(); a11y_pass(d)
    check(open(os.path.join(d, "scrA.pa.yaml")).read() == before, "a11y pass is idempotent")
    # CA12 (guide §217c): a ModernCardGallery without AccessibleLabel gets one; one that has a label keeps it
    dg = tempfile.mkdtemp()
    write_app(dg, None, [screen("scrCG", [ctl("cgProjects", "ModernCardGallery", {"Items": "Projects", "Title": "ThisItem.Title"}),
                                          ctl("cgKept", "ModernCardGallery", {"Items": "Projects", "AccessibleLabel": '"Kept"'})])])
    a11y_pass(dg)
    cg = open(os.path.join(dg, "scrCG.pa.yaml")).read()
    check(cg.count("AccessibleLabel:") == 2 and '"Kept"' in cg, "negative: a11y pass labels an unlabelled ModernCardGallery, keeps an existing label")
    # NEGATIVES, each must fire its own rule
    neg = {
        "DUP_NAME": screen("scrB", [label("lblX", '"a"'), label("lblX", '"b"')]),
        "ACCESSIBLE_LABEL_UNKNOWN": screen("scrC", [ctl("lblY", "Label", {"Text": '"a"', "AccessibleLabel": '"a"', "TabIndex": 0, "FocusedBorderThickness": 2})]),
        "RESERVED_WITH_FIELD": screen("scrD", [label("lblZ", 'With({empty: true}, If(empty, "a", "b"))')]),
        "COALESCE_EMPTY_COMPARE": screen("scrE", [label("lblW", 'If(Coalesce(varT, "") = "", "none", varT)')]),
        "DELEGATION_SMELL": screen("scrF", [gallery("galQ", "Filter(Requests, Status <> \"Done\")", [], "Requests")]),
    }
    for rule, sc in neg.items():
        dd = tempfile.mkdtemp(); write_app(dd, None, [sc]); rr = lint([dd], None)
        check(rule in [x["rule"] for x in rr["findings"]], f"negative: {rule} fires")
    dd = tempfile.mkdtemp(); open(os.path.join(dd, "scrG.pa.yaml"), "w").write("Screens:\n  scrG:\n    Properties:\n      OnVisible: =Set(a: 1)\n")
    check("YAML_PARSE" in [x["rule"] for x in lint([dd], None)["findings"]], "negative: plain ': ' formula is a YAML_PARSE error")
    try:
        gallery("galBad", "[]", [], "x", variant="galleryVertical"); check(False, "negative: bad Gallery variant raises")
    except ValueError:
        check(True, "negative: bad Gallery variant raises at build time")
    check(lint([tempfile.mkdtemp()], None)["files_read"] == 0, "floor: an empty folder reads 0 files (CLI exits 4)")
    # EVENT_EMPTY_DEFAULT (guide §185o): bare "=", empty and missing fire; the builder's =false and Studio's ="" do not
    hdr = "ComponentDefinitions:\n  cmpEv:\n    DefinitionType: CanvasComponent\n    CustomProperties:\n"
    ev = lambda d: "      OnGo:\n        PropertyKind: Event\n        DisplayName: OnGo\n        ReturnType: None\n" + (f"        Default: {d}\n" if d is not None else "")
    for label_, d, want in (("bare =", "=", 1), ("missing", None, 1), ("=false", "=false", 0), ('=""', '=""', 0)):
        dd = tempfile.mkdtemp(); open(os.path.join(dd, "cmpEv.pa.yaml"), "w").write(hdr + ev(d))
        rr = lint([dd], None); n = [x["rule"] for x in rr["findings"]].count("EVENT_EMPTY_DEFAULT")
        check(rr["files_read"] == 1 and n == want, f"{'negative' if want else 'false-positive'}: Event Default {label_} -> EVENT_EMPTY_DEFAULT x{n} (want {want})")
    dd = tempfile.mkdtemp(); write_app(dd, None, [], [component("cmpB", [prop_event("OnGo")], [])]); rr = lint([dd], None)
    check("EVENT_EMPTY_DEFAULT" not in [x["rule"] for x in rr["findings"]] and rr["files_read"] == 1, "false-positive: prop_event() builder output is clean")
    # Nov-2026 controls: the builders must emit what Studio saved (CA04/CA05), and lint clean
    dg = data_grid("dgWork", "'Work progress tracker'", [data_grid_column("colTitle", "Title", "Title"),
                   data_grid_column("colPri", "Priority", "Priority", text="ThisItem.Priority.Value")], page_size=50, searchable=True)
    sc = screen("scrH", [container("cntH", "Vertical", [dg, metric_card("mcOpen", "Open items", 'Text(CountRows(Requests))'),
                                                       number_input("numQty", '"Quantity"', default="1")])])
    dd = tempfile.mkdtemp(); write_app(dd, None, [sc]); rr = lint([dd], _load_catalog())
    yml = open(os.path.join(dd, "scrH.pa.yaml")).read()
    check("Control: ModernDataGrid@1.7.0" in yml and "Variant: Textual" in yml and "Pagination: =Pagination.Number" in yml,
          "Nov-2026 builders: data grid emits the version, column Variant and Pagination Studio saved")
    errs = [x for x in rr["findings"] if x["severity"] == "error"]
    check(not errs, f"Nov-2026 builders lint without errors ({[x['rule'] for x in errs]})")
    # SELECT_QUEUED_READ (guide §188c): reading a variable the Selected button sets fires; Select as the last step does not
    rec = button("btnRecalcT", '"r"', "Set(varRec, txtA.Text)")
    for label_, body, want in (("read after Select", "Select(btnRecalcT);\nPatch(Things, Defaults(Things), varRec)", 1),
                               ("Select last, no read", "Patch(Things, Defaults(Things), {A: txtA.Text});\nSelect(btnRecalcT)", 0),
                               ("other variable read", "Select(btnRecalcT);\nSet(varOther, 1);\nNotify(Text(varOther))", 0)):
        dd = tempfile.mkdtemp(); write_app(dd, None, [screen("scrS", [rec, button("btnSaveT", '"s"', body)])]); rr = lint([dd], None)
        n = [x["rule"] for x in rr["findings"]].count("SELECT_QUEUED_READ")
        check(rr["files_read"] == 1 and n == want, f"{'negative' if want else 'false-positive'}: {label_} -> SELECT_QUEUED_READ x{n} (want {want})")
    # DELEGATION_SMELL v2 (guide §192): one negative per cause App Checker reported on CA11, plus the look-alikes that
    # must stay clean. Kinds are checked exactly, so a case cannot pass by firing a different cause (memory:
    # refusal tests pass on the wrong rule).
    dcases = [
        ("negative", "aggregate: CountRows over a list", "", 'Text(CountRows(Requests))', ["aggregate"]),
        ("negative", "not-equal inside NESTED brackets (v1's [^)]* regex missed this)", "",
         'CountRows(Filter(Requests, Status.Value = If(varA, "a", "b") && Title <> "z"))', ["aggregate", "not-equal"]),
        ("negative", "not: !IsBlank in a predicate", "", 'Average(Filter(Requests, !IsBlank(Rating)), Rating)', ["aggregate", "not"]),
        ("negative", "in: text search", "", 'Filter(Requests, "abc" in Title)', ["in"]),
        ("negative", "column-fn: Lower on a column", "", 'Filter(Requests, Lower(Title) = "x")', ["column-fn"]),
        ("negative", "a bare named formula over a list is still the list", "Open = Filter(Requests, Status.Value = \"Open\");",
         'CountRows(Open)', ["aggregate"]),
        ("false-positive", "a collection is local", "", 'ClearCollect(colR, Requests); CountRows(colR)', []),
        ("false-positive", "a FirstN-wrapped named formula is local (POWERFX 4.7)", "Recent = FirstN(Requests, 500);",
         'CountRows(Recent)', []),
        ("false-positive", "<> inside a string literal", "", 'Filter(Requests, Title = "a <> b")', []),
        ("false-positive", "scalar Min/Max of numbers is not a table aggregate (ST01 shape)", "",
         'Set(varR, Min(OnHand / Max(Reorder, 1), 1))', []),
        ("negative", "Sum over a list the app filters elsewhere still fires", "",
         'Set(varT, Sum(Requests, Amount)); Set(varN, CountRows(Filter(Requests, Status.Value = "A")))', ["aggregate"]),
        ("false-positive", "a With field holding nested records is local (FA01 shape)", "",
         'With({cfg: If(varA, ForAll(T, {Order: 1, Title: "a"}), T2), st: "x"}, LookUp(cfg, Lower(Title) = "a"))', []),
        ("negative", "reading a non-delegable named formula is flagged at the reader (CA06 shape)",
         "TotalOpen = CountRows(Filter(Requests, Status.Value <> \"Done\"));", 'Text(TotalOpen)', ["named"]),
        ("false-positive", "a FirstN named formula behind // comment blocks is still recognised (CA06 shape)",
         "// ===== header =====\n// note; with a semicolon\nRecent =\nFirstN(Requests, 500);", 'CountRows(Recent)', []),
        ("false-positive", "<> and in inside // and /* */ comments (the kit's own list template)", "",
         'Filter(Requests,\n    // `in` and `<>` do not delegate\n    /* not in, not <> */ Status.Value = "Open")', []),
        ("negative", "a real <> AFTER a comment still fires", "",
         'Filter(Requests,\n    // a note\n    Status.Value <> "Done")', ["not-equal"]),
        ("false-positive", "Lower on User()/a variable, not a column", "",
         'Set(varQ, "a"); Filter(Requests, Email = Lower(User().Email) && Title = Lower(varQ))', []),
        ("false-positive", "in against a local table", "", 'ClearCollect(colR, Requests); Filter(colR, Title in ["a", "b"])', []),
        ("false-positive", "= on a choice column delegates", "", 'Filter(Requests, Status.Value = "Open")', []),
        # [@Name] (guide §217a): Studio's 'Start with data' template writes every list reference as [@'Projects List'];
        # v2 resolved no root through the brackets, so CA12's Distinct over the list was invisible to the lint
        ("negative", "shaping through [@'List'] (CA12 shape)", "",
         "ClearCollect(colB, Ungroup(ForAll(Distinct([@'Projects List'], Title) As C, {Rows: Filter([@'Projects List'], Title = C.Value)}), Rows))",
         ["shaping"]),
        ("negative", "not-equal through [@Requests]", "", 'Filter([@Requests], Status.Value <> "Done")', ["not-equal"]),
        ("false-positive", "= through [@'List'] delegates", "", "Filter([@'Projects List'], Status.Value = \"Open\")", []),
        ("false-positive", "[@col] naming a collection is still local", "", 'ClearCollect(colR, Requests); CountRows([@colR])', []),
    ]
    for kind_, label_, formulas, body, want in dcases:
        dd = tempfile.mkdtemp()
        write_app(dd, app(formulas=formulas) if formulas else None, [screen("scrD2", [button("btnD2", '"d"', body)])])
        rr = lint([dd], None)
        got = sorted({x["message"].split("]")[0][1:] for x in rr["findings"] if x["rule"] == "DELEGATION_SMELL"
                      and x["where"].startswith("btnD2")})
        check(rr["files_read"] >= 1 and got == sorted(want), f"{kind_}: DELEGATION_SMELL {label_} -> {got} (want {sorted(want)})")
    # --source dataverse (guide §201): aggregates over a Dataverse table delegate, so only the aggregate kind is dropped
    for label_, body, want in [
        ("positive: aggregate is NOT flagged on a Dataverse source", 'Text(CountRows(Filter(Requests, Status.Value = "A")))', []),
        ("false-positive guard: not-equal is STILL flagged on a Dataverse source", 'Filter(Requests, Status.Value <> "Done")', ["not-equal"]),
        ("false-positive guard: aggregate plus not-equal keeps only not-equal", 'CountRows(Filter(Requests, Title <> "z"))', ["not-equal"]),
    ]:
        dd = tempfile.mkdtemp()
        write_app(dd, None, [screen("scrD2", [button("btnD2", '"d"', body)])])
        rr = lint([dd], None, "dataverse")
        got = sorted({x["message"].split("]")[0][1:] for x in rr["findings"] if x["rule"] == "DELEGATION_SMELL"
                      and x["where"].startswith("btnD2")})
        check(rr["files_read"] >= 1 and got == sorted(want), f"source=dataverse: {label_} -> {got} (want {sorted(want)})")
    # APP SPEED (W3 Q6, guide §211b): each rule fires on its negative and stays quiet on its look-alikes, counted exactly
    def speed(label_, screens_, want, rule, a=None, kind_="negative"):
        nonlocal fails
        dd = tempfile.mkdtemp(); write_app(dd, a, screens_); rr = lint([dd], None)
        n = [x["rule"] for x in rr["findings"]].count(rule)
        check(rr["files_read"] >= 1 and n == want, f"{kind_}: {rule} {label_} -> x{n} (want {want})")
    three = 'ClearCollect(colReq, Requests);\nClearCollect(colStaff, Staff);\nSet(varSite, LookUp(Sites, Code = "KL"))'
    speed("three loads in OnStart", [screen("scrO1", [text("txtSpdO1", '"x"')])], 1, "ONSTART_HEAVY", app(OnStart=three))
    speed("two loads in OnStart", [screen("scrO2", [text("txtSpdO2", '"x"')])], 0, "ONSTART_HEAVY", app(OnStart='ClearCollect(colReq, Requests);\nClearCollect(colStaff, Staff)'), "false-positive")
    speed("variables and a literal table", [screen("scrO3", [text("txtSpdO3", '"x"')])], 0, "ONSTART_HEAVY",
          app(OnStart='Set(varTheme, "x");\nClearCollect(colMenu, Table({a: 1}, {a: 2}));\nSet(varMe, User().Email);\nSet(varN, CountRows(colMenu))'), "false-positive")
    speed("two loads in sequence", [screen("scrC1", [text("txtSpdC1", '"x"')], OnVisible='ClearCollect(colA, Requests);\nClearCollect(colB, Staff)')], 1, "LOAD_NOT_CONCURRENT")
    speed("the same loads in Concurrent", [screen("scrC2", [text("txtSpdC2", '"x"')], OnVisible='Concurrent(\n    ClearCollect(colA, Requests),\n    ClearCollect(colB, Staff)\n)')], 0, "LOAD_NOT_CONCURRENT", None, "false-positive")
    speed("a second load that reads the first", [screen("scrC3", [text("txtSpdC3", '"x"')], OnVisible='ClearCollect(colA, Requests);\nClearCollect(colB, Filter(colA, Status.Value = "Open"))')], 0, "LOAD_NOT_CONCURRENT", None, "false-positive")
    keyp = text_input("txtSpdQ", '"Search"', '"Search"', TriggerOutput="TriggerOutput.Keypress")
    galq = lambda nm, src: gallery(nm, f"Filter({src}, StartsWith(Title, txtSpdQ.Text))", [], '"rows"')
    speed("Keypress input in a list Filter", [screen("scrQ1", [keyp, galq("galSpdA", "Requests")])], 1, "SEARCH_NO_DELAY")
    speed("builder default (Delayed)", [screen("scrQ2", [text_input("txtSpdQ", '"Search"', '"Search"'), galq("galSpdB", "Requests")])], 0, "SEARCH_NO_DELAY", None, "false-positive")
    speed("Keypress input over a local collection", [screen("scrQ3", [keyp, galq("galSpdC", "colReq")], OnVisible="ClearCollect(colReq, [1])")], 0, "SEARCH_NO_DELAY", None, "false-positive")
    speed("classic input without DelayOutput", [screen("scrQ4", [ctl("txtSpdQ", "Classic/TextInput", {"Default": '""'}), galq("galSpdD", "Requests")])], 1, "SEARCH_NO_DELAY")
    speed("classic input with DelayOutput true", [screen("scrQ5", [ctl("txtSpdQ", "Classic/TextInput", {"Default": '""', "DelayOutput": "true"}), galq("galSpdE", "Requests")])], 0, "SEARCH_NO_DELAY", None, "false-positive")
    onb = screen("scrXB", [ctl("frmXB", "Classic/TextInput", {"Default": '""', "DelayOutput": "true"})])
    speed("Reset of a control on another screen (CA08 shape)", [screen("scrXA", [button("btnXA", '"new"', "Reset(frmXB);\nNavigate(scrXB)")]), onb], 1, "CROSS_SCREEN_REF")
    speed("Navigate to a screen and a same-screen control", [screen("scrXA", [ctl("txtXA", "Classic/TextInput", {"Default": '""', "DelayOutput": "true"}), button("btnXA", '"go"', "Reset(txtXA);\nNavigate(scrXB)")]), onb], 0, "CROSS_SCREEN_REF", None, "false-positive")
    speed("a control on the StartScreen", [screen("scrXA", [button("btnXA", '"go"', "Reset(frmXB)")]), onb], 0, "CROSS_SCREEN_REF", app(StartScreen="scrXB"), "false-positive")
    speed("a record field named like a control", [screen("scrXA", [button("btnXA", '"go"', "Navigate(scrXB, ScreenTransition.None, {frmXB: 1})")]), onb], 0, "CROSS_SCREEN_REF", None, "false-positive")
    speed("ClearCollect of a filtered list", [screen("scrW1", [text("txtSpdW1", '"x"')], OnVisible='ClearCollect(colR, Filter(Requests, Status.Value = "Open"))')], 1, "WIDE_COLUMN_READ")
    speed("ShowColumns around the source", [screen("scrW2", [text("txtSpdW2", '"x"')], OnVisible='ClearCollect(colR, ShowColumns(Filter(Requests, Status.Value = "Open"), Title, Status))')], 0, "WIDE_COLUMN_READ", None, "false-positive")
    speed("a copy of a local collection", [screen("scrW3", [text("txtSpdW3", '"x"')], OnVisible='ClearCollect(colR, [1, 2]);\nClearCollect(colS, colR)')], 0, "WIDE_COLUMN_READ", None, "false-positive")
    # P36 rules (guide §228a-b): each with a negative and a false-positive control
    def p36(label_, screens_, comps_, want, rule, kind_="negative"):
        nonlocal fails
        dd = tempfile.mkdtemp(); write_app(dd, None, screens_, comps_); rr = lint([dd], None)
        n = [x["rule"] for x in rr["findings"]].count(rule)
        check(rr["files_read"] >= 1 and rr["controls_read"] >= 1 and n == want, f"{kind_}: {rule} {label_} -> x{n} (want {want})")
    cmpT = component("cmpTstA", [prop_input("Caption", "Text", '"x"')], [text("txtCmpA", "Parent.Caption")])
    cmpV = component("cmpTstB", [prop_input("Caption", "Text", '"x"')], [text("txtCmpB", "Parent.Caption")], Visible="true")
    p36("Visible on the definition", [screen("scrP1", [instance("inP1", "cmpTstB")])], [cmpV], 1, "COMPONENT_DEF_VISIBLE")
    p36("Visible on the instance only", [screen("scrP2", [instance("inP2", "cmpTstA", {"Visible": "true"})])], [cmpT], 0, "COMPONENT_DEF_VISIBLE", "false-positive")
    p36("instance in a gallery template container", [screen("scrP3", [gallery("galP3", "colX", [container("cntP3", "Horizontal", [instance("inP3", "cmpTstA")])], '"rows"')])], [cmpT], 1, "COMPONENT_IN_GALLERY")
    p36("instance in a container on the screen", [screen("scrP4", [container("cntP4", "Vertical", [instance("inP4", "cmpTstA")]), gallery("galP4", "colX", [text("txtP4", "ThisItem.Value")], '"rows"')])], [cmpT], 0, "COMPONENT_IN_GALLERY", "false-positive")
    p36("Default a text literal", [screen("scrP5", [ctl("ddP5", "ModernDropdown", {"Items": "colTerms", "Default": '"30 days"', "AccessibleLabel": '"Term"'})])], [], 1, "DROPDOWN_DEFAULT_LITERAL")
    p36("Default a record", [screen("scrP6", [ctl("ddP6", "ModernDropdown", {"Items": "colTerms", "Default": "First(Self.Items)", "AccessibleLabel": '"Term"'})])], [], 0, "DROPDOWN_DEFAULT_LITERAL", "false-positive")
    p36("28 px pill with default padding", [screen("scrP7", [container("cntP7", "Horizontal", [text("txtP7", '"Approved"', Height="28")])])], [], 1, "MODERNTEXT_UNDER_MIN_HEIGHT")
    p36("28 px pill, padding 0 and min 28 (kit row_pill)", [screen("scrP8", [container("cntP8", "Horizontal", [text("txtP8", '"Approved"', Height="28", PaddingTop="0", PaddingBottom="0", LayoutMinHeight="28")])])], [], 0, "MODERNTEXT_UNDER_MIN_HEIGHT", "false-positive")
    p36("28 px text straight on the screen", [screen("scrP9", [text("txtP9", '"x"', Height="28")])], [], 0, "MODERNTEXT_UNDER_MIN_HEIGHT", "false-positive")
    print(f"selftest: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    if sys.argv[1] == "--selftest":
        sys.exit(selftest())
    if sys.argv[1] == "lint":
        sys.exit(lint_cli(sys.argv[2:]))
    if sys.argv[1] == "a11y":
        lab = {}
        if "--labels" in sys.argv:
            lab = json.load(open(sys.argv[sys.argv.index("--labels") + 1], encoding="utf-8"))
        sys.exit(a11y_pass(sys.argv[2], lab))
    print(__doc__); sys.exit(2)
