// P38 'AFE Spend' code app (review test 2): one screen, spend against approval per AFE.
// Data: native Dataverse tsc_afestatus (written nightly by Fabric, CJ_Status_Out) joined to tsc_afe for the requester.
// Theme tokens: PitchSidePro v2 Executive (light), same hex as the canvas app's nfColor. Fictional company, synthetic data.
import { useEffect, useMemo, useState } from "react";
import { getContext } from "@microsoft/power-apps/app";
import { StatusService, AfeService } from "./dataSources";
import "./App.css";

type Row = { afe: string; title: string; asset: string; requester: string; approved: number; actual: number; committed: number;
             eac: number; pct: number; flag: boolean; status: string; refreshed: string };
type Load = "loading" | "error" | "ready";
const rm = (v: number) => "RM " + (v / 1e6).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "m";
const pc = (v: number) => (v * 100).toLocaleString("en-MY", { maximumFractionDigits: 1 }) + "%";
const SCALE = 1.4, LINE = 1.1;

function Bullet({ r }: { r: Row }) {
  const w = Math.min(100, (r.pct / SCALE) * 100);
  return (
    <div className="bul" role="img" aria-label={`EAC ${pc(r.pct)} of approval; line at 110%`}>
      <div className={r.flag ? "bar bad" : "bar"} style={{ width: w + "%" }} />
      <i style={{ left: (LINE / SCALE) * 100 + "%" }} />
    </div>
  );
}

export default function App() {
  const [rows, setRows] = useState<Row[]>([]);
  const [state, setState] = useState<Load>("loading");
  const [me, setMe] = useState("");
  const [mine, setMine] = useState(true);
  const [asset, setAsset] = useState("All");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let live = true;
    (async () => {
      setState("loading");
      try {
        const ctx = await getContext();
        const upn = (ctx?.user?.userPrincipalName ?? "").toLowerCase();
        const [st, af] = await Promise.all([StatusService.all(), AfeService.all()]);
        const byNo = new Map(af.map((a) => [a.afeNo, a]));
        const out: Row[] = st.map((s) => {
          const a = byNo.get(s.afeNo);
          return { afe: s.afeNo, title: a?.title ?? "", asset: s.asset, requester: (a?.requesterEmail ?? "").toLowerCase(),
                   approved: s.approved, actual: s.actual, committed: s.committed, eac: s.eac, pct: s.pct, flag: s.flag,
                   status: s.status, refreshed: s.refreshed };
        });
        if (live) { setMe(upn); setRows(out); setState("ready"); }
      } catch (e) {
        console.error(e);
        if (live) setState("error");
      }
    })();
    return () => { live = false; };
  }, [tick]);

  const assets = useMemo(() => ["All", ...Array.from(new Set(rows.map((r) => r.asset))).sort()], [rows]);
  const shown = useMemo(() => rows
    .filter((r) => !mine || r.requester === me)
    .filter((r) => asset === "All" || r.asset === asset)
    .sort((a, b) => b.pct - a.pct), [rows, mine, me, asset]);
  const refreshed = rows.reduce((m, r) => (r.refreshed > m ? r.refreshed : m), "");

  return (
    <main className="page">
      <header className="hdr">
        <h1>AFE spend</h1>
        <p>Committed = actual plus open POs. The line marks 110% of approval: past it, raise a supplement.</p>
      </header>
      <div className="chips" role="toolbar" aria-label="Filters">
        <button className={mine ? "chip on" : "chip"} aria-pressed={mine} onClick={() => setMine(true)}>Mine</button>
        <button className={!mine ? "chip on" : "chip"} aria-pressed={!mine} onClick={() => setMine(false)}>All</button>
        <label className="chip sel">Asset
          <select value={asset} onChange={(e) => setAsset(e.target.value)} aria-label="Asset">
            {assets.map((a) => <option key={a}>{a}</option>)}
          </select>
        </label>
        <span className="chip static">Sort: EAC % &#9660;</span>
      </div>

      {state === "loading" && <div className="state"><div className="spin" aria-hidden="true" /><span>Loading spend</span></div>}
      {state === "error" && <div className="state"><b>Could not load spend</b><span>Dataverse did not answer. Check your connection and try again.</span>
        <button className="b1" onClick={() => setTick(tick + 1)}>Try again</button></div>}
      {state === "ready" && shown.length === 0 && <div className="state"><b>No AFEs to show</b>
        <span>{mine ? "You have no AFEs with spend yet. Switch to All to see every AFE." : "Spend appears after the nightly refresh."}</span></div>}

      {state === "ready" && shown.length > 0 && (<>
        <table className="tb">
          <thead><tr><th className="l">AFE</th><th className="r">Approved</th><th className="r">Actual</th><th className="r">Committed</th>
            <th className="r">EAC</th><th className="l">EAC vs approval (line = 110%)</th></tr></thead>
          <tbody>{shown.map((r) => (
            <tr key={r.afe} className={r.flag ? "flag" : ""}>
              <td className="l"><b>{r.afe}</b><br /><span className="mut">{r.title}</span></td>
              <td className="r">{rm(r.approved)}</td><td className="r">{rm(r.actual)}</td><td className="r">{rm(r.committed)}</td>
              <td className="r">{rm(r.eac)}</td>
              <td className="l"><Bullet r={r} /><span className={r.flag ? "pct bad" : "pct"}>{pc(r.pct)}</span>
                {r.flag && <span className="tag">Supplement needed</span>}</td>
            </tr>))}</tbody>
        </table>
        <div className="cards">{shown.map((r) => (
          <article key={r.afe} className={r.flag ? "card flag" : "card"}>
            <b>{r.afe}</b><div className="mut">{r.title}</div><Bullet r={r} />
            <div className="mut">EAC {rm(r.eac)}, {pc(r.pct)} of {rm(r.approved)} (line = 110%). Actual {rm(r.actual)}; committed {rm(r.committed)}.</div>
            {r.flag && <span className="tag">Supplement needed</span>}
          </article>))}</div>
      </>)}
      <footer className="mut foot">Spend from Fabric, refreshed each night{refreshed ? `. Last refresh ${refreshed}` : ""}. Teduh Samudera Energy is fictional · synthetic data</footer>
    </main>
  );
}
