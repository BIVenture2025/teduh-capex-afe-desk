// P38 adapter: the generated Dataverse services (src/generated, from `pa app add data-source`) mapped to the screen's shape.
// Columns by LOGICAL name (S288 candidate: display names can clash with system columns, e.g. "Status").
import { Tsc_afestatusesService, Tsc_afesService } from "./generated";

type Res<T> = { data?: T[]; error?: unknown; success?: boolean };
function rows<T>(r: Res<T>, what: string): T[] {
  if (r.error || r.success === false) throw new Error(what + ": " + JSON.stringify(r.error ?? "failed"));
  return r.data ?? [];
}
const n = (v?: number | null) => (typeof v === "number" ? v : 0);
const when = (iso?: string) => {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : d.toLocaleString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
};

export type StatusRow = { afeNo: string; asset: string; approved: number; actual: number; committed: number; eac: number; pct: number;
                          flag: boolean; status: string; refreshed: string };
export type AfeRow = { afeNo: string; title: string; requesterEmail: string };

export const StatusService = {
  async all(): Promise<StatusRow[]> {
    const r = await Tsc_afestatusesService.getAll({
      select: ["tsc_afeno", "tsc_assetcode", "tsc_approved", "tsc_actual", "tsc_committed", "tsc_eac", "tsc_eacpct",
               "tsc_supplementneeded", "tsc_status", "tsc_refreshedon"], maxPageSize: 500 });
    return rows(r as Res<any>, "AFE status").map((s: any) => ({
      afeNo: s.tsc_afeno ?? "", asset: s.tsc_assetcode ?? "", approved: n(s.tsc_approved), actual: n(s.tsc_actual),
      committed: n(s.tsc_committed), eac: n(s.tsc_eac), pct: n(s.tsc_eacpct), flag: !!s.tsc_supplementneeded,
      status: s.tsc_status ?? "", refreshed: when(s.tsc_refreshedon) }));
  },
};
export const AfeService = {
  async all(): Promise<AfeRow[]> {
    const r = await Tsc_afesService.getAll({ select: ["tsc_afeno", "tsc_title", "tsc_requesteremail"], maxPageSize: 500 });
    return rows(r as Res<any>, "AFEs").map((a: any) => ({ afeNo: a.tsc_afeno ?? "", title: a.tsc_title ?? "", requesterEmail: a.tsc_requesteremail ?? "" }));
  },
};
