import { useState } from "react";

import { Card } from "../../components/ui/Card";
import { fetchFiscalReference } from "../../services/lumenService";
import type { FiscalReferenceEntry, FiscalReferenceSearchResponse } from "../../types/fiscalReference";

function value(item: string | boolean | null) {
  if (item === null) return "-";
  if (typeof item === "boolean") return item ? "Sim" : "Não";
  return item;
}

function ReferenceRows({ rows, kind }: { rows: FiscalReferenceEntry[]; kind: "cnae" | "lc116" | "tribnac" }) {
  if (!rows.length) return <p className="empty-copy">Nenhuma correlação encontrada nesta fonte.</p>;
  return <div className="detail-grid compact">
    {rows.map((row) => (
      <article key={`${row.source_kind}-${row.source_row_number}`}>
        {kind === "cnae" ? <><span>Item LC 116</span><strong>{value(row.lc116_item_formatted)}</strong><span>{value(row.lc116_description)}</span><span>Alíquota: {row.iss_rate ? `${(Number(row.iss_rate) * 100).toFixed(2)}%` : "-"}</span><span>Tributar fora: {value(row.allows_tax_outside)}</span></> : null}
        {kind === "lc116" ? <><span>{value(row.lc116_item_formatted)} → NBS</span><strong>{value(row.nbs_formatted)}</strong><span>{value(row.nbs_description)}</span><span>IndOp: {value(row.indop_code)}</span><span>cClassTrib: {value(row.class_trib_code)}</span></> : null}
        {kind === "tribnac" ? <><span>NBS {value(row.nbs_formatted)}</span><strong>cTribNac {value(row.trib_nac_code)}</strong><span>{value(row.trib_nac_description)}</span><span>cClassTrib: {value(row.class_trib_code)} | CST: {value(row.cst_code)}</span><span>IndOp: {value(row.indop_code)}</span></> : null}
      </article>
    ))}
  </div>;
}

export function FiscalReferencePage() {
  const [type, setType] = useState<"cnae" | "nbs">("cnae");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<FiscalReferenceSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search() {
    setLoading(true);
    setError(null);
    try {
      setResult(await fetchFiscalReference(type, query));
    } catch (reason) {
      setResult(null);
      setError(reason instanceof Error ? reason.message : "Não foi possível consultar a base de referência.");
    } finally {
      setLoading(false);
    }
  }

  return <div className="cards-grid">
    <Card>
      <div className="card-header"><h3>Consulta Fiscal</h3></div>
      <p className="card-body-copy">Base de referência CNAE, LC 116, NBS e IBS/CBS</p>
      <p className="card-body-copy">Base de referência global. A empresa e a competência selecionadas no Lumen não alteram esta consulta.</p>
      <div className="filter-row">
        <button className={type === "cnae" ? "filter-chip active" : "filter-chip"} type="button" onClick={() => setType("cnae")}>CNAE</button>
        <button className={type === "nbs" ? "filter-chip active" : "filter-chip"} type="button" onClick={() => setType("nbs")}>NBS</button>
        <input aria-label="Código para consulta" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={type === "cnae" ? "Ex.: 6201-5/01" : "Ex.: 1.1502.10.00"} />
        <button className="primary-button" type="button" disabled={!query || loading} onClick={() => void search()}>{loading ? "Consultando..." : "Consultar"}</button>
      </div>
      {error ? <p className="empty-copy">{error}</p> : null}
    </Card>
    {result ? <>
      <Card><div className="card-header"><h3>{type.toUpperCase()} {result.normalized_query}</h3></div><p className="card-body-copy">{result.summary.reference_rows} correlações de referência encontradas.</p></Card>
      <Card><div className="card-header"><h3>CNAE → LC 116</h3></div><ReferenceRows rows={result.cnae_lc116} kind="cnae" /></Card>
      <Card><div className="card-header"><h3>LC 116 → NBS</h3></div><ReferenceRows rows={result.lc116_nbs} kind="lc116" /></Card>
      <Card><div className="card-header"><h3>NBS → IBS/CBS</h3></div><ReferenceRows rows={result.tribnac_nbs} kind="tribnac" /></Card>
    </> : null}
  </div>;
}
