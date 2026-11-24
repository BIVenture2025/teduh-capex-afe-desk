"""PBIR visual primitives, lifted from P34's report generator (06_Report/generator/build_report.py, Session 10),
which harvested them from P30's delivered byConnection generator. W4 Q7, guide 212d.

Schema versions: visualContainer 2.11.0, page 2.1.0, pagesMetadata 1.1.0, report 3.3.0 (SCHEMA). When you EDIT an
existing project, match its versions instead (CLAUDE.md section 6); this kit is for new reports.
Colours and the millions set come from the project's theme: call configure(...) once before building; defaults
are P34's MyLifeInLegoBricks values. Arguments that default to a colour (accent=D1) bind at import: pass them
explicitly when the theme differs. LABELS collects every display label for the copy check.
Equivalence with P34 is a test (lib/tests/test_lib.py): each primitive returns the same JSON as P34's own.
W6 (guide 215c): a shown legend hides its title by default (`legend_title=False`, the shape P24 delivered on a lineChart
at visualContainer 2.11.0: legend `showTitle` false); the W4 review found P34's legends titled "segment" and "kind".
`legend_title=None` reproduces P34's legend exactly. Still open: KPI labels are measure names."""
import itertools
import json
import os

SCHEMA = {
    "visual": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.11.0/schema.json",
    "page": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
    "pages": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
    "report": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
    "version": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
    "pbir": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
    "pbip": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
    "platform": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
}
INK, SEC, TER = "#27221F", "#635E57", "#6E6961"
CARD_BG, BORDER, PAGE_BG = "#FFFFFB", "#E1DACB", "#F2EFE6"
HEAT_MAX = "#E39A92"
D1, D2, D3, D4, D5 = "#165E83", "#2F9AAB", "#1B3A5C", "#6C8FB3", "#B23A34"
MILLIONS = set()      # measure names shown in millions on KPI cards (a project passes its own set to configure)
LABELS = []
_SETTINGS = ("INK", "SEC", "TER", "CARD_BG", "BORDER", "PAGE_BG", "HEAT_MAX", "D1", "D2", "D3", "D4", "D5", "MILLIONS")


def configure(**kw):
    """Set theme colours (INK, SEC, TER, CARD_BG, BORDER, PAGE_BG, HEAT_MAX, D1..D5) and MILLIONS for this build."""
    g = globals()
    for k, v in kw.items():
        if k not in _SETTINGS:
            raise KeyError(f"configure: unknown setting {k}")
        g[k] = set(v) if k == "MILLIONS" else v


def b(v):        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
def num(v):      return {"expr": {"Literal": {"Value": f"{v}D"}}}
def lng(v):      return {"expr": {"Literal": {"Value": f"{v}L"}}}
def s(v):        return {"expr": {"Literal": {"Value": "'" + v.replace("'", "''") + "'"}}}
def color(hexv): return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hexv}'"}}}}}


def measure(entity, name, display=None):
    LABELS.append(("td", display or name))
    p = {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": name}},
         "queryRef": f"{entity}.{name}", "nativeQueryRef": name, "active": True}
    if display:
        p["displayName"] = display
    return p


def column(entity, prop, display=None):
    p = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
         "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop, "active": True}
    if display:
        p["displayName"] = display
        LABELS.append(("td", display))
    return p


def by_measure(entity, name, desc=True):
    return {"sort": [{"field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}},
                                            "Property": name}},
                      "direction": "Descending" if desc else "Ascending"}]}


def by_column(entity, prop, desc=False):
    return {"sort": [{"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}},
                                           "Property": prop}},
                      "direction": "Descending" if desc else "Ascending"}]}


def cat_filter(fname, entity, prop, values):
    """Categorical visual filter, shape from P25. Returns ONE filter entry."""
    return {"name": fname,
            "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "type": "Categorical",
            "filter": {"Version": 2,
                       "From": [{"Name": "f", "Entity": entity, "Type": 0}],
                       "Where": [{"Condition": {"In": {
                           "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}},
                                                       "Property": prop}}],
                           "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in values]}}}]}}


def topn_filter(fname, dim, prop, fact, mname, n):
    """Form A of topn_subquery_filter.md: exactly name/field/type/filter."""
    return {"name": fname,
            "field": {"Column": {"Expression": {"SourceRef": {"Entity": dim}}, "Property": prop}},
            "type": "TopN",
            "filter": {"Version": 2,
                       "From": [{"Name": "subquery", "Type": 2, "Expression": {"Subquery": {"Query": {
                           "Version": 2,
                           "From": [{"Name": "g", "Entity": dim, "Type": 0},
                                    {"Name": "g1", "Entity": fact, "Type": 0}],
                           "Select": [{"Column": {"Expression": {"SourceRef": {"Source": "g"}},
                                                  "Property": prop}, "Name": "field"}],
                           "OrderBy": [{"Direction": 2, "Expression": {"Measure": {
                               "Expression": {"SourceRef": {"Source": "g1"}}, "Property": mname}}}],
                           "Top": n}}}},
                                {"Name": "g", "Entity": dim, "Type": 0}],
                       "Where": [{"Condition": {"In": {
                           "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "g"}},
                                                       "Property": prop}}],
                           "Table": {"SourceRef": {"Source": "subquery"}}}}}]}}


def chrome(title=None, subtitle=None, alt=None, panel=True):
    vco = {}
    if panel:
        vco["background"] = [{"properties": {"show": b(True), "color": color(CARD_BG),
                                             "transparency": num(0)}}]
        vco["border"] = [{"properties": {"show": b(True), "color": color(BORDER), "radius": num(6)}}]
    else:
        vco["background"] = [{"properties": {"show": b(False)}}]
    if title:
        LABELS.append(("h3", title))
        vco["title"] = [{"properties": {"show": b(True), "text": s(title), "fontSize": num(11),
                                        "bold": b(True), "fontColor": color(INK),
                                        "titleWrap": b(True)}}]
    if subtitle:
        LABELS.append(("td", subtitle))
        vco["subTitle"] = [{"properties": {"show": b(True), "text": s(subtitle), "fontSize": num(9),
                                           "fontColor": color(SEC), "titleWrap": b(True)}}]
    if alt:
        vco["general"] = [{"properties": {"altText": s(alt)}}]
    return vco


def pos(x, y, w, h, z, tab):
    return {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": tab}


def textbox(name, p, paragraphs, panel=False, flag=False, accent=D1):
    """paragraphs: list of (text, size_pt, hex, bold, italic). flag=True marks a declared
    disclaimer/caveat block: check_wording.py must not grade it as a label."""
    paras = []
    for text, size, col, bold, ital in paragraphs:
        LABELS.append(("flag" if flag else "td", text))
        style = {"fontSize": f"{size}pt", "color": col}
        if bold:
            style["fontWeight"] = "bold"
        if ital:
            style["fontStyle"] = "italic"
        paras.append({"textRuns": [{"value": text, "textStyle": style}],
                      "horizontalTextAlignment": "left"})
    vco = {}
    if panel:
        vco["background"] = [{"properties": {"show": b(True), "color": color(CARD_BG),
                                             "transparency": num(0)}}]
        vco["border"] = [{"properties": {"show": b(True), "color": color(accent), "radius": num(8)}}]
        vco["padding"] = [{"properties": {"left": lng(14), "right": lng(14),
                                          "top": lng(10), "bottom": lng(10)}}]
    else:
        vco["background"] = [{"properties": {"show": b(False)}}]
        vco["border"] = [{"properties": {"show": b(False)}}]
        vco["padding"] = [{"properties": {"left": lng(2), "right": lng(2),
                                          "top": lng(0), "bottom": lng(0)}}]
    return {"$schema": SCHEMA["visual"], "name": name, "position": p,
            "visual": {"visualType": "textbox",
                       "objects": {"general": [{"properties": {"paragraphs": paras}}]},
                       "visualContainerObjects": vco}}


def nav(name, p):
    return {"$schema": SCHEMA["visual"], "name": name, "position": p,
            "visual": {
                "visualType": "pageNavigator",
                "objects": {
                    "pages": [{"properties": {"showHiddenPages": b(False)}}],
                    "shape": [{"properties": {"tileShape": s("pill")}, "selector": {"id": "default"}}],
                    "text": [
                        {"properties": {"fontSize": num(8), "fontColor": color(SEC)},
                         "selector": {"id": "default"}},
                        {"properties": {"fontSize": num(8), "fontColor": color(CARD_BG)}, "selector": {"id": "selected"}},
                        {"properties": {"fontSize": num(8), "fontColor": color(D1)}, "selector": {"id": "hover"}},
                    ],
                    "fill": [
                        {"properties": {"fillColor": color(CARD_BG)}, "selector": {"id": "default"}},
                        {"properties": {"fillColor": color(D3)}, "selector": {"id": "selected"}},
                        {"properties": {"fillColor": color(BORDER)}, "selector": {"id": "hover"}},
                    ],
                    "outline": [{"properties": {"lineColor": color(BORDER)}, "selector": {"id": "default"}}],
                },
                "visualContainerObjects": {"background": [{"properties": {"show": b(False)}}]},
                "drillFilterOtherVisuals": True,
            },
            "howCreated": "InsertVisualButton"}


def rule(name, p):
    return {"$schema": SCHEMA["visual"], "name": name, "position": p,
            "visual": {"visualType": "shape",
                       "objects": {
                           "shape": [{"properties": {"tileShape": s("rectangleRoundedByPixel"),
                                                     "rectangleRoundedCurve": lng(0)}}],
                           "fill": [{"properties": {"show": b(True), "fillColor": color(BORDER)}}],
                       },
                       "visualContainerObjects": {"general": [{"properties": {"altText": s("")}}]}}}


def kpi_card(name, p, measures, alt, accent=D1, vsize=19):
    v = _kpi_card(name, p, measures, alt, accent, vsize)
    for m in measures:
        if m[1] in MILLIONS:
            v["visual"]["objects"]["value"].append({"properties": {"labelDisplayUnits": num(1000000), "labelPrecision": lng(1)},
                                                    "selector": {"metadata": f"{m[0]}.{m[1]}"}})
    return v


def _kpi_card(name, p, measures, alt, accent=D1, vsize=19):
    """ONE multi-measure cardVisual per KPI row; bucket is `Data`."""
    return {"$schema": SCHEMA["visual"], "name": name, "position": p,
            "visual": {
                "visualType": "cardVisual",
                "query": {"queryState": {"Data": {"projections": [measure(*m) for m in measures]}},
                          "sortDefinition": {"isDefaultSort": True}},
                "objects": {
                    "layout": [{"properties": {
                        "style": s("Cards"), "backgroundShow": b(True),
                        "backgroundFillColor": color(CARD_BG),
                        "rectangleRoundedCurve": lng(8), "borderWidth": num(1),
                        "borderColor": color(BORDER), "paddingUniform": lng(14),
                        "columnPadding": lng(12)}, "selector": {"id": "default"}}],
                    "accentBar": [{"properties": {
                        "show": b(True), "position": s("Left"), "color": color(accent),
                        "width": num(3)}, "selector": {"id": "default"}}],
                    "value": [{"properties": {"fontSize": num(vsize), "bold": b(True),
                                              "fontColor": color(D3), "labelDisplayUnits": num(1)},
                               "selector": {"id": "default"}}],
                    "label": [{"properties": {"show": b(True), "fontSize": num(9),
                                              "fontColor": color(SEC), "textWrap": b(True)},
                               "selector": {"id": "default"}}],
                    "outline": [{"properties": {"show": b(False)}, "selector": {"id": "default"}}],
                },
                "visualContainerObjects": {
                    "background": [{"properties": {"show": b(False)}}],
                    "general": [{"properties": {"altText": s(alt)}}],
                },
            }}


def cartesian(name, vtype, p, cat, ys, title, subtitle, alt, colors=None, sort=None,
              legend=False, labels=True, filters=None, inner_padding=None, min_cat=None, legend_title=False):
    q = {"queryState": {"Category": {"projections": [cat]}, "Y": {"projections": ys}},
         "sortDefinition": sort if sort is not None else {"isDefaultSort": True}}
    objs = {
        "valueAxis": [{"properties": {"gridlineShow": b(False), "show": b(False), "labelDisplayUnits": num(1)}}],
        "categoryAxis": [{"properties": {"gridlineShow": b(False), "fontSize": num(9),
                                         "labelColor": color(INK)}}],
        "labels": [{"properties": {"show": b(labels), "fontSize": num(9), "color": color(INK), "labelDisplayUnits": num(1)}}],
        "legend": [{"properties": {"show": b(legend), "fontSize": num(9), "labelColor": color(SEC)}}],
    }
    if legend and legend_title is not None:
        objs["legend"][0]["properties"]["showTitle"] = b(legend_title)
    if inner_padding is not None:
        objs["categoryAxis"][0]["properties"]["innerPadding"] = lng(inner_padding)
    if min_cat is not None:
        # Not sufficient on its own (S6b pass 4: bars still scrolled); kept as an option.
        objs["categoryAxis"][0]["properties"]["preferredCategoryWidth"] = num(min_cat)
    if colors:
        if len(colors) == 1:
            objs["dataPoint"] = [{"properties": {"fill": color(colors[0])}}]
        else:
            objs["dataPoint"] = [{"properties": {"fill": color(c)},
                                  "selector": {"metadata": ys[i]["queryRef"]}}
                                 for i, c in enumerate(colors)]
    v = {"$schema": SCHEMA["visual"], "name": name, "position": p,
         "visual": {"visualType": vtype, "query": q, "objects": objs,
                    "visualContainerObjects": chrome(title, subtitle, alt),
                    "drillFilterOtherVisuals": True}}
    if filters:
        v["filterConfig"] = {"filters": filters}
    return v


def matrix(name, p, rows, values, title, subtitle, alt, sort=None, filters=None):
    objs = {
        "general": [{"properties": {"textSize": num(9)}}],
        "columnHeaders": [{"properties": {"fontColor": color(SEC), "backColor": color(CARD_BG),
                                          "outline": s("BottomOnly")}}],
        "rowHeaders": [{"properties": {"fontColor": color(INK), "outline": s("None"),
                                       "wordWrap": b(False)}}],
        "values": [{"properties": {"fontColorPrimary": color(INK), "fontColorSecondary": color(INK)}}],
        "grid": [{"properties": {"gridVertical": b(False), "gridHorizontal": b(True),
                                 "gridHorizontalColor": color(BORDER), "rowPadding": num(3)}}],
    }
    v = {"$schema": SCHEMA["visual"], "name": name, "position": p,
         "visual": {"visualType": "matrix",
                    "query": {"queryState": {"Rows": {"projections": rows},
                                             "Values": {"projections": values}},
                              "sortDefinition": sort if sort else {"isDefaultSort": True}},
                    "objects": objs,
                    "visualContainerObjects": chrome(title, subtitle, alt)}}
    if filters:
        v["filterConfig"] = {"filters": filters}
    return v


def table_ex(name, p, cols, title, subtitle, alt, sort=None, filters=None):
    """tableEx: single flat `Values` bucket. NEVER carries drillFilterOtherVisuals."""
    v = {"$schema": SCHEMA["visual"], "name": name, "position": p,
         "visual": {"visualType": "tableEx",
                    "query": {"queryState": {"Values": {"projections": cols}},
                              "sortDefinition": sort if sort else {"isDefaultSort": True}},
                    "objects": {
                        "columnHeaders": [{"properties": {"fontColor": color(SEC),
                                                          "backColor": color(CARD_BG),
                                                          "fontSize": num(9), "bold": b(True)}}],
                        "values": [{"properties": {"fontColor": color(INK), "fontSize": num(9)}}],
                        "grid": [{"properties": {"gridVertical": b(False),
                                                 "gridHorizontalColor": color(BORDER),
                                                 "rowPadding": num(3)}}],
                        "total": [{"properties": {"totals": b(False)}}],
                    },
                    "visualContainerObjects": chrome(title, subtitle, alt)}}
    if filters:
        v["filterConfig"] = {"filters": filters}
    return v

def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    with open(path, encoding="utf-8") as fh:   # every JSON validated on write
        json.load(fh)


def mtext(entity, prop):
    return {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}}


def takeaway(name, p, entity, prop, size=11, colr=SEC, bold=False, alt="Page takeaway, computed from the data."):
    """Transparent shape whose container TITLE is a DAX text measure (P29 subTitle-to-measure shape)."""
    return {"$schema": SCHEMA["visual"], "name": name, "position": p,
            "visual": {"visualType": "shape",
                       "objects": {"shape": [{"properties": {"tileShape": s("rectangleRoundedByPixel")}}],
                                   "fill": [{"properties": {"show": b(False)}}],
                                   "outline": [{"properties": {"show": b(False)}}]},
                       "visualContainerObjects": {
                           "title": [{"properties": {"show": b(True), "text": mtext(entity, prop), "fontSize": num(size),
                                                     "bold": b(bold), "fontColor": color(colr), "titleWrap": b(True),
                                                     "background": color(PAGE_BG)}}],
                           "background": [{"properties": {"show": b(False)}}],
                           "border": [{"properties": {"show": b(False)}}],
                           "general": [{"properties": {"altText": s(alt)}}]}}}


def slicer(name, p, entity, prop, alt):
    return {"$schema": SCHEMA["visual"], "name": name, "position": p,
            "visual": {"visualType": "slicer",
                       "query": {"queryState": {"Values": {"projections": [column(entity, prop)]}}},
                       "objects": {"data": [{"properties": {"mode": s("Dropdown")}}],
                                   "header": [{"properties": {"show": b(False)}}],
                                   "items": [{"properties": {"textSize": num(9)}}]},
                       "visualContainerObjects": {"general": [{"properties": {"altText": s(alt)}}],
                                                  "stylePreset": [{"properties": {"name": s("")}}]},
                       "drillFilterOtherVisuals": True},
            "filterConfig": {"filters": [not_blank(f"fNotBlank{next(_NB):02d}", entity, prop)]}}


def chart(name, vtype, p, cat, ys, title, subtitle, alt, series=None, colors=None, sort=None, legend=False,
          labels=True, filters=None, margin=None, min_cat=None, value_axis=False, legend_title=False):
    v = cartesian(name, vtype, p, cat, ys, title, subtitle, alt, colors=colors, sort=sort, legend=legend,
                  labels=labels, filters=filters, min_cat=min_cat, legend_title=legend_title)
    if all(y["field"].get("Measure", {}).get("Property") in MILLIONS for y in ys):
        v["visual"]["objects"]["labels"][0]["properties"].update({"labelDisplayUnits": num(1000000), "labelPrecision": lng(1)})
        v["visual"]["objects"]["valueAxis"][0]["properties"].update({"labelDisplayUnits": num(1000000), "labelPrecision": lng(0)})
    if value_axis:
        va = v["visual"]["objects"]["valueAxis"][0]["properties"]
        va["show"] = b(True); va["fontSize"] = num(9); va["labelColor"] = color(SEC)
    if margin is not None:
        v["visual"]["objects"]["categoryAxis"][0]["properties"]["maxMarginFactor"] = lng(margin)
    if series is not None:
        v["visual"]["query"]["queryState"]["Series"] = {"projections": [series]}
        v["visual"]["objects"].pop("dataPoint", None)
    return v


def xmatrix(name, p, rows, cols, values, title, subtitle, alt):
    v = matrix(name, p, rows, values, title, subtitle, alt)
    v["visual"]["query"]["queryState"]["Columns"] = {"projections": cols}
    return v


_NB = itertools.count(1)  # filter names must be unique report-wide (PBIR_FILTER_NAME_DUPLICATE_GLOBAL)


def not_blank(fname, entity, prop):
    """Advanced 'is not blank' filter: hides the blank member Direct Lake shows in a dimension (S10)."""
    col = {"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": prop}}
    return {"name": fname,
            "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "type": "Advanced",
            "filter": {"Version": 2, "From": [{"Name": "f", "Entity": entity, "Type": 0}],
                       "Where": [{"Condition": {"Not": {"Expression": {"Comparison": {
                           "ComparisonKind": 0, "Left": col, "Right": {"Literal": {"Value": "null"}}}}}}}]}}


def bool_filter(fname, entity, prop, val=True):
    f = cat_filter(fname, entity, prop, [])
    f["filter"]["Where"][0]["Condition"]["In"]["Values"] = [[{"Literal": {"Value": "true" if val else "false"}}]]
    return f
