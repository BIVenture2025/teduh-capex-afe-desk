# Project Brief — 38) Capex AFE Desk (Teduh Samudera)

`Solution type: Combined Solution · Data: sample · Delivery: portfolio`
`Start mode: stack open · Brief accepted by the owner: 2026-11-23`

## 1. What done looks like
A capex control desk for Teduh Samudera Energy (the fictional Malaysian upstream operator of P35, now on the capital side). A project engineer raises an AFE (authority for expenditure) for a capital project in an app, with the estimate by cost element and by year. Finance checks it, then the approver named by the limits-of-authority (LOA) matrix decides in Approvals. Fabric lands the purchase-order commitments and the general-ledger actuals for every AFE, works out spend against the approved amount and an estimate at completion (EAC), and flags any AFE heading more than 10% over its approval. That flag goes back to the app, where the engineer raises a supplementary AFE from it. A Power BI report shows the whole capex portfolio: budget, approved, committed, actual, EAC, the watchlist and how long approvals take. One AFE travels the full loop end to end. Published as a portfolio piece: repo, guide, deck, card, live report link.

## 2. Who it is for
Purpose: portfolio. All data is synthetic and says so in the app, the report and the repo.

| Role | Top three tasks |
|---|---|
| Project engineer (requester) | 1. Raise an AFE with its estimate and phasing in a few minutes, and see who will approve it before submitting. 2. See where each of my AFEs stands and what was decided. 3. See spend against approval for my AFEs, and raise a supplement when one is flagged. |
| Finance controller (first check) | 1. Check that an AFE fits the asset's capex budget. 2. Return it with a reason or pass it to the LOA approver. 3. See every open AFE and its age. |
| LOA approver (asset manager, GM projects, CEO) | 1. Decide an AFE with the budget position and the estimate in front of me. 2. See supplements against the original approval. 3. Know what I approved this year. |
| Capex controller / CFO (report) | 1. Where is the capex portfolio against budget and approval this year? 2. Which AFEs will overrun, by how much, and who owns them? 3. Are approvals slow, and at which tier? |

## 3. Questions the solution must answer
| # | Question | Where |
|---|---|---|
| Q1 | Can I raise this AFE, and who will approve it? | App: New AFE, step 3 (route preview) |
| Q2 | Where does each of my AFEs stand, and what was decided? | App: My AFEs (list, detail) |
| Q3 | How much of my AFE is committed and spent, and what is the EAC? | App: spend screen (code-app probe screen) |
| Q4 | Which AFEs need a supplement? | App: flag on My AFEs; report: Watchlist |
| Q5 | Capex YTD: budget, approved, committed, actual, EAC, by asset | Report: Scoreboard |
| Q6 | Which AFEs are over or heading over approval, by how much? | Report: Watchlist |
| Q7 | How long do approvals take, by tier and by step? | Report: Approvals |
| Q8 | For one AFE: phasing, cost elements, POs, approval history | Report: AFE detail (drill-through) |

## 4. Stack card
**Options (stack open, 2026-11-23).** Both use pattern 4, App round trip (P34), and the Developer environment `US Environment` (Dataverse `<yourorg>.crm.dynamics.com`), which is in the US region: code apps need Dataverse, and generative pages run only in US environments (Learn, checked 2026-11-23). Fabric stays on the Malaysia West trial capacity.

- **Lean:** Lakehouse medallion by notebooks and lake views; Dataverse tables for AFEs, LOA matrix and decisions; canvas app plus ONE code-app screen (the spend screen, review test 2); one approval flow (finance check, then LOA tier); Copy jobs both ways run through DataFactory MCP (review test 3); Direct Lake model; PBIR report, 4 pages.
- **Showcase:** Lean, plus a model-driven "Capex review desk" with one generative page (finance overview), an ML overrun-risk score per AFE in Gold (Skill 3 route R5), and an Activator alert when committed plus actual passes 90% of approval. Costs about two extra work blocks; generative pages and Activator are not established here.

**Owner picked Lean (2026-11-23).** Showcase items (generative page, ML overrun score, Activator) go to `01_Design/NEXT_VERSION.md`.

| Layer | Block (Lean; Showcase adds marked +) | Why | Status (`STACK_MENU.md`) | Probe |
|---|---|---|---|---|
| Source | Generated sample: ERP extracts (POs, GL actuals), capex budget, seeded AFE history; control totals frozen by query | sample label | proven | no |
| Store (platform) | Lakehouse `TeduhCapex` Bronze/Silver/Gold, notebooks + materialized lake views | pattern 1 | proven | P6 |
| Store (app) | Dataverse tables: AFE, AFE line, LOA tier, decision log, AFE status (from Fabric) | approvals need a record store; Copy jobs proven both ways | proven (P34); MCP reads refused, Web API reads (S248) | P2 |
| Movement | Copy job Dataverse → Lakehouse (AFEs, decisions); Copy job Lakehouse → Dataverse (AFE status, upsert on GUID); run and status by DataFactory MCP | review test 3 | proven by wizard; MCP run live (S243) | **P5** |
| Orchestration | Pipeline: notebooks with verdict gates; a notebook starts the Copy jobs (S178) | proven | proven | no |
| App | Canvas app on Dataverse (Home, New AFE 3 steps, My AFEs) from the kit | proven | proven (P34) | no |
| App screen | Spend screen as a **code app** (React, `pac code push`) | review test 2 | not established | **P3** |
| + App | Model-driven Capex review desk with one **generative page** | showcase | not established; US only | **P4** |
| Flow | Dataverse row submitted → Approvals (finance) → Approvals (LOA tier) → update → Outlook email | proven (S156, S167) | proven | P1 |
| + Analytics | ML overrun-risk score per open AFE | showcase | proven route (P34) | no |
| + Alert | Activator on Gold AFE status | showcase | not established | P7 |
| Model | Direct Lake on OneLake over Gold | proven | proven | no |
| Report | PBIR, 4 pages, theme from `Themes/` | proven | proven | no |
| Mockup | HTML Design Package only; Claude Design canvas **skipped by the owner (2026-11-23)**, route stays partial, not tested | owner | partial | none |
| Ops | Git repo + `deploy_items.py` or plan, Variable Library | proven | proven | no |
| Package | Solution export, `validate_solution_zip.py --cross-tenant` | proven | proven | no |
| Publish | Repo, Pages guide, deck, card, live report link | portfolio | proven | no |

**SETTLED domains to read every session:** FAB, RPT, MOD, PP, HOST.

## 5. Components
| # | Component | Must or nice | Workstream | Built? |
|---|---|---|---|---|
| 1 | Generator: ~60 AFEs on 4 assets + corporate, 2024–2026; POs, GL actuals, capex budget; seeded decided AFEs; frozen control totals | must | data | |
| 2 | Lakehouse Bronze/Silver/Gold (AFE spend, EAC, headroom, supplement flag) with DQ checks | must | data | |
| 3 | Dataverse tables and seed (LOA tiers, assets, seeded AFEs) | must | app data | |
| 4 | LOA routing rule: Python oracle, Power Fx UDF, flow expression agreeing on every test vector | must | rules | |
| 5 | Approval flow (finance check, LOA tier, write back, email) | must | flows | |
| 6 | Canvas app: Home, New AFE (3 steps), My AFEs (list, detail, supplement from flag) | must | app | |
| 7 | Spend screen as a code app (or canvas if P3 fails) | must | app | |
| 8 | Copy jobs both ways, run and read back through DataFactory MCP | must | movement | |
| 9 | Pipeline with verdict gates; one full end-to-end run | must | orchestration | |
| 10 | Direct Lake model, measure contracts, regression baseline | must | model | |
| 11 | Report: Scoreboard, Watchlist, Approvals, AFE detail | must | report | |
| 12 | Solution export, cross-tenant check, install notes | must | package | |
| 13 | Repo, guide, deck, card, live report link | must | publish | |
| 14 | Theme `Themes/PitchSidePro_Theme_v2_Executive.json` in report and app (owner, 2026-11-23) | must | report, app | |

## 6. Constraints
- Host: Cowork. Portal and Studio steps in Claude in Chrome; Windows steps by `.cmd` through computer use. Free tooling.
- **One session for the whole project (owner, 2026-11-23).** Gates are stops inside it.
- Wording: simple, no AI-looking text. Malaysian upstream terms checked in Design ("AFE", "supplementary AFE", "LOA", "WP&B").
- Culture `en-MY`, RM, Malaysia time.

**Target-environment gate**
| Gate | Answer | How known |
|---|---|---|
| Dataverse in the target environment? | Yes: `US Environment` (Developer, unitedstates), `<yourorg>.crm.dynamics.com` | queried (FlowAgent, m365, 2026-11-23) |
| Installer's role | Owner, admin | owner records |
| Licences | Developer plan gives the owner premium (Dataverse, code apps) | Developer environment rule |
| Every connector standard? | Dataverse is premium (covered by Developer plan); Approvals, Outlook standard | connector tier |
| Connections present | Dataverse Connected; Office 365 Outlook Connected; **Approvals missing** (create in P1) | queried 2026-11-23 |
| Who installs, when | Owner, at Publish (export), no second-tenant install | this brief |

## 7. Data
`sample`: Teduh Samudera Energy (fictional, screened in P35). Assets Teduh Utara, Teduh Selatan, Teduh Timur (offshore fields), the onshore gas terminal, and corporate. AFE types: drilling, facilities, pipeline, IT and buildings, abandonment study. Amounts from RM 0.4m to RM 80m. LOA (owner, 2026-11-23): finance controller check first, then asset manager up to RM 5m, GM projects up to RM 25m, CEO above. Supplement when EAC passes approval by more than 10%. About 60 AFEs (about 45 decided and seeded, about 8 open created live, the rest closed), ~1,500 POs, ~12,000 GL lines. Control totals frozen by query.

## 8. Probes
| Probe | What it proves | How measured | Result | Fallback or kill |
|---|---|---|---|---|
| P1 Connectors and DLP | Dataverse, Approvals, Outlook run together in `US Environment` | Connections Connected; flow activates | Dataverse and Office 365 Outlook Connected (FlowAgent, 2026-11-23); Approvals connection created in Build step 1; DLP confirmed when the flow activates | Kill Outlook if DLP refuses; notify through the record |
| P2 Dataverse by Web API | Create tables and read rows by `m365 request` | table create + read back | **PASS (read, 2026-11-23):** `m365 request` WhoAmI on `<yourorg>` returns user and org ids; table create in Build step 1 | Studio table designer in Chrome |
| P3 Code app | One screen pushed as a code app and opened in Power Apps | feature on; `pac code push` returns an app id; app opens and reads one Dataverse row | **PASS (2026-11-24 00:08):** Windows has node v24.14.1, npm 11.21.1, git; Vite template by degit; `@microsoft/power-apps-cli` (npm, `pa app`) init with browser sign-in, build, push: "App pushed successfully", app id `<your-code-app-id>`, added to the preferred solution; the player opens it as "P38 AFE Spend". One fix round: `call` doubled the `^` in `@^1.3.0` (cmd trap). The Dataverse read moves to Build. Log `_probe/p38_20261124/` | **Kill if push fails after one fix round: screen built in canvas; STACK_MENU row stays not established with the finding** |
| P4 + Generative page (showcase; not run, owner picked Lean) | A page created by description in a model-driven app | page saved and shows rows | — | Kill if not offered or refused: page dropped |
| P5 DataFactory MCP | Copy job created or run and read back by MCP | `run_copy_job` → Completed; row count in Lakehouse | Token expired; `authenticate_interactive` opened a sign-in the session cannot click (WebView). Owner signs in at Build step "Copy jobs" | Create in the wizard (S161), still run by MCP |
| P6 Fabric workspace | Workspace on the Malaysia West trial capacity | Core MCP create + list | **PASS (2026-11-23):** workspace `TeduhCapex-Dev` `aaaaaaaa-0000-4000-8000-000000000001` on trial `14e682a7…` Malaysia West | — |
| P7 + Activator (showcase; not run) | Rule on a Gold table fires an email | one test fire | — | Kill: alert dropped |
| P8 Cost capture | Usage saved at every gate | usage JSON in `_sessions/_cost/` | G1 read saved `_sessions/_cost/S1_G1_usage.json` (26 requests) | record not capturable |

## 9. Session plan
Budget: Combined Solution 7 to 8. **Split at G2: waived (owner, 2026-11-23): one session for the whole project.** Usage read at every gate and before every long step.

| # | Gate | Stage and work | Model | Ends when |
|---|---|---|---|---|
| 1a | G1 | Discover: brief, probes P1, P2, P3, P5, P6 | Opus | Owner accepts the brief |
| 1b | G2 | Design: mockups of every page and screen, architecture, Dataverse and Lakehouse design, model sheet, measure contracts, LOA contract, tests, subagent audit | Opus | Owner approves the package |
| 1c | G3 | Build: data, Dataverse, flow, app, code app, Copy jobs, pipeline, model, report; one AFE end to end | Opus (one session) | Exit checks pass |
| 1d | G4 | Publish: build record, export, repo, guide, deck, card | Opus | Links checked from outside |
| 1e | G5 | Close: C1 to C8, lessons, cost row, `session_close.py` v2 | Opus | Close passes |

## 10. Exit criteria and review
- [ ] Every must component built (section 5).
- [ ] LOA rule: oracle, UDF and flow agree on every vector.
- [ ] One AFE submitted, checked, approved, landed in Fabric, flagged, and its status read back in the app.
- [ ] Copy jobs run by DataFactory MCP, landing counted in the Lakehouse (S243, S175).
- [ ] Every save, deploy and run read back (S259, S279, S280); `INFO.MEASURES` state after every model deploy (S276).
- [ ] Report: both validators, render gate, Desktop capture of every page; regenerate and diff before Publish (S255).
- [ ] Solution cross-tenant check exit 0; public tree grepped for path fragments (S256).
- [ ] `session_close.py` v2 passes with no unnamed cost gap.

Second-agent review: the LOA routing rule (component 4) and the EAC and supplement logic in Gold (component 2).

## 11. Revision log
| Rev | Date | What changed and who decided |
|---|---|---|
| 1 | 2026-11-23 | Draft. Owner picked: Capex AFE desk, stack open, sample + portfolio, Claude Design canvas skipped, one session for the whole project. |
| 2 | 2026-11-23 | **Owner accepted the brief (G1).** Lean stack; LOA two steps, RM 5m / RM 25m, 10% supplement trigger kept; theme PitchSidePro v2 Executive. |
| 3 | 2026-11-24 | Discover probes: P2, P3, P6 PASS; P1 two of three connections, Approvals created in Build; P5 sign-in deferred to Build (owner present). |
| 4 | 2026-11-24 | Design: package audited by a second agent (29 findings, all fixed; table in the guide). Data as generated: 63 AFEs (60 originals, 3 supplements; 30 open, 27 closed, 3 rejected), 455 POs, 4,718 GL lines, 132 decision rows; originals by tier T1 28, T2 18, T3 14. Live AFEs get no ERP rows, so the end-to-end flag test is seeded TSE-AFE-26-009 plus a live supplement (exit criterion 3 reads that way). Contract changes: supplement = one contingency line; LOA total counts pending supplements; T1 = the asset's own manager; tsc_assetbudget added for the approval card; flow assigns AFE numbers. Build stays on Opus in this one session (owner waived the split; cost: cache read per request grows with length, S287, usage read before every long step). |
| 5 | 2026-11-24 | **Owner approved the Design Package (G2)** (`01_Design/P38_CapexAFE_Package.html`). Scope frozen; new ideas go to `01_Design/NEXT_VERSION.md`. Install rehearsal waived (owner). Build continues in this session on Opus (owner). |
| 6 | 2026-11-24 | Build done except review test 3 (DataFactory MCP sign-in pending the owner) and the approval loop (two approvals pending). Pipeline Completed over REST; negative control failed as designed. Solution exported, cross-tenant 0/0. Publish prepared locally; public push waits for the owner's yes. Close in the next session (`_sessions/NEXT_KICKOFF_P38_FINISH.md`). |
