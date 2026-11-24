# P38 Capex AFE Desk: build record

Combined Solution, sample data, portfolio. Fictional company Teduh Samudera Energy. Built in one session (owner, 2026-11-23).
Every line below cites the read-back that proves it. Status as of 24 Nov 2026 10:00 MYT (session 2, the finish).

## Components (brief section 5)

| # | Component | Built? | Proof (read back) |
|---|---|---|---|
| 1 | Generator and frozen control totals | Built | `gen_teduh_capex.py` byte-identical on regeneration; 63 AFEs, 455 POs RM 678,909,900.00, 4,718 GL lines RM 584,437,639.23 |
| 2 | Lakehouse Bronze/Silver/Gold with checks | Built | NB_ERP verdict ERP_OK (readback equals control totals); NB_Gold verdict GOLD_OK: 57 families equal the frozen oracle, 0 diffs, 30 open, 4 flagged |
| 3 | Dataverse tables and seed | Built | 8 tables in solution TeduhCapex; counts read back: 63 AFEs, 314 lines, 122 phasing, 132 decisions, 4 LOA tiers, 5 assets |
| 4 | LOA rule in three places | Built | Python oracle self-test; Power Fx tcTier 18 of 18 (scrRuleTest); deployed flow expressions 18 of 18 (`test_flow_rule.py`); live run tier T3 for RM 81.5m |
| 5 | Approval flow | Built | `P38 AFE approval` statecode 1 / statuscode 2; live run on TSE-AFE-26-022 Succeeded: finance check approved, then LOA T3 (CEO) approved; Set_approved, Log_approved and Mail_approved ran, reject and return branches skipped; Dataverse shows 26-022 Approved with 2 decision rows |
| 6 | Canvas app | Built | compile_canvas 0 errors; accessibility 0; App Checker 1 (kit's unused gblToast); reload + sync proves the saved app equals src |
| 7 | Spend screen as a code app | Built | `P38 AFE Spend` pushed; renders tsc_afestatus live (26-009: RM 66.20m approved, EAC RM 81.46m, 123%) |
| 8 | Copy jobs both ways | Built | CJ_AFE_In 6/6 tables, 640 read = 640 written; CJ_Status_Out 57 + 15 rows upserted; both run again inside the pipeline started by the DataFactory MCP (item 9); CJ_Status_Out also run alone by MCP `run_copy_job` (job e75f297c, Completed in 40 s, read back with `get_copy_job_run_status`) |
| 9 | Pipeline with verdict gates, one full run | Built | REST run Completed in 7m9s (t32); blocked control Failed with P38_GOLD_BLOCKED (t33); DataFactory MCP `run_pipeline` job 33861717 Completed in 10m57s, read back with `get_pipeline_run_status`. Loop closed: TSE-AFE-26-009 approved RM 66.2m to RM 81.5m, EAC 123% to 99.95%, flagged AFEs 4 to 3 (Dataverse tsc_afestatus refreshed 01:48 UTC) |
| 10 | Direct Lake model | Built | 14 tables, 17 relationships, 42 measures; INFO.MEASURES 0 not ready (Fabric IQ); checks: 57 families, 30 open, 4 flagged, GL RM 584,437,639.23, PO RM 678,909,900 |
| 11 | Report | Built | 5 pages, 55 visuals; validate_pbip 0 errors; official CLI 0 errors 0 warnings; all 5 pages judged in the service renderer, 6 defects fixed (L13, L14) |
| 12 | Solution export, cross-tenant check, install notes | Built | Both apps added to TeduhCapex; unmanaged export TeduhCapex_1_0_0_0.zip (164 KB); cross-tenant check 0 errors 0 warnings; INSTALL_NOTES.md. Install rehearsal waived by the owner |
| 13 | Repo, guide, deck, card, report link | Built (no report link) | Public repo BIVenture2025/teduh-capex-afe-desk (6f30f0d, 148 files, scrub 0 BLOCK); guide on Pages 200 with 4 of 4 images decoding; card 25 on the portfolio site (b24b3c2); deck 7 slides (local). No public report link: the report lives in a trial tenant, as for P35 to P37 |
| 14 | Theme PitchSidePro v2 Executive in report and app | Built | report theme file registered; app nfColor tokens from pa_theme.py |

## Deviations from the approved design
1. AFE numbers are assigned by the app at submit (the design had the flow do it). Next number read back: TSE-AFE-26-022.
2. AFE detail is a normal page with an AFE slicer saved on TSE-AFE-26-009, not drill-through.
3. The 110% trigger is a second bar beside EAC % (clustered), not a reference line.
4. The Approver role slicer does not filter "Waiting for a decision".
5. Copy jobs were created and first run in the Fabric wizard (S161 fallback); the DataFactory MCP later ran the whole pipeline once the sign-in completed.

## Known limits
- Home tile "Need a supplement" counts all flagged AFEs, not only the user's.
- The kit's App.Formulas leaves one App Checker warning (unused gblToast) and one compile warning (typed empty holiday list).
- Spend in the app and report is as at the last nightly run; a supplement shows after Copy in, Gold and Copy out.
- Regenerate and diff (S255), run at Close: model 20 files and report 66 files identical to `02_Build/estate/fabric/`.
