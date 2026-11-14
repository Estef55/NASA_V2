import { useCallback, useEffect, useState } from 'react';
import { BookOpen, CheckCircle2, Database, ExternalLink, Info, RefreshCw, ShieldAlert } from 'lucide-react';

type Props = {
  api: (path: string, token: string, init?: RequestInit) => Promise<any>;
  token: string;
  lang: 'en' | 'es';
  role: string;
  onRefreshed?: () => Promise<void>;
};

const copy = {
  en: {
    eyebrow: 'SCIENTIFIC CONTEXT & PROVENANCE',
    title: 'NASA & CSA scientific consultation',
    subtitle: 'Verified reference catalog and public study metadata. Strictly separated from crew telemetry, personal baselines, and demo records.',
    refresh: 'Query & verify NASA sources',
    refreshing: 'Querying…',
    refreshedOk: 'Official sources queried.',
    refreshedFail: 'Verification completed with unavailability errors:',
    tabSources: 'Official sources',
    tabDomains: 'Hazards, risks & programs',
    tabData: 'Public NASA data (OSDR)',
    officialChallenge: 'Official scientific reference',
    publicApi: 'NASA Open Data API (OSDR)',
    openSite: 'Open official site',
    openStudy: 'Open original NASA study',
    limitations: 'Access limitations',
    availability: 'Data availability',
    format: 'Format',
    units: 'Units',
    population: 'Population / context',
    license: 'License / terms',
    lastChecked: 'Last check',
    lastSuccess: 'Last successful query',
    neverChecked: 'Not yet checked in runtime',
    noSuccessYet: 'No successful live query recorded yet',
    httpVerifiedBadge: 'Official source verified via HTTP',
    restrictedDataBadge: 'Restricted data access',
    hrpRoleTitle: 'NASA HRP (Human Research Program)',
    hrpRoleDesc: 'Provides the scientific framework of the main hazards and risks of human spaceflight. LÁTIRA uses this classification as context to organize and explain the relevance of its tracking indicators.',
    osdrRoleTitle: 'NASA OSDR (Open Science Data Repository)',
    osdrRoleDesc: 'Provides access to public scientific research metadata on health and spaceflight. LÁTIRA queries and displays available records to provide scientific context and facilitate exploration of related research.',
    nonSubstitutionNotice: 'NASA resources complement LÁTIRA’s scientific context. Public studies do not represent personal astronaut measurements and do not replace individual monitoring records.',
    hazardsTitle: 'NASA Five Hazards of Human Spaceflight',
    hazardsNote: 'Contextual mission hazards only — not automatic personal measurements.',
    notMeasured: 'Context only · not measured automatically',
    hazardHealthLink: 'Health monitoring relevance',
    hazardIndicators: 'Related LÁTIRA indicators',
    risksTitle: 'NASA HRP Risk Domains & LÁTIRA Indicators',
    risksNote: 'Maps scientific research areas to existing LÁTIRA indicators without changing clinical thresholds.',
    mappedTo: 'Related LÁTIRA indicators',
    relevanceHeader: 'Scientific explanation',
    noDirectSignal: 'No direct LÁTIRA indicator',
    programsTitle: 'Ongoing NASA HRP Research Programs',
    scientificRelation: 'Scientific relation / objective',
    programDisclaimer: 'Reference program only: LÁTIRA does not access private participant data or NASA flight instruments.',
    csaTitle: 'CSA CANS & ISS Space Science Context',
    cansStatus: 'CSA CANS: Reference only · NOT connected',
    dataTitle: 'Verified Public NASA OSDR Study Metadata',
    dataEmpty: 'No public OSDR study records cached yet. An administrator can run the NASA query to retrieve public records.',
    dataUnavailableNotice: 'NASA OSDR is temporarily unavailable. Previously stored records remain visible below without inventing new data.',
    studyId: 'Study identifier',
    studyTitle: 'Original study title',
    organismLabel: 'Organism / studied population',
    missionProgramLabel: 'Program or mission',
    materialLabel: 'Sample / material type',
    assayLabel: 'Analysis technology / method',
    obsDate: 'Available date or period',
    queriedAt: 'LÁTIRA query date',
    classification: 'Record classification',
    quality: 'Quality indicator',
    origin: 'API endpoint',
    notAvailableInRecord: 'Not available in NASA record',
    syncReportTitle: 'Latest NASA OSDR query result',
    fetchedCount: 'Retrieved',
    insertedCount: 'New saved',
    updatedCount: 'Updated',
    retainedCount: 'Previously stored',
    totalCount: 'Total in cache',
    syncStateMap: {
      new: 'New record',
      updated: 'Updated',
      previously_stored: 'Previously stored',
    } as Record<string, string>,
    statusMap: {
      reference_only: 'Catalogued scientific reference',
      catalogued: 'Catalogued scientific reference',
      available: 'Public API available',
      connected: 'API connected (verified live query)',
      unavailable: 'Source temporarily unavailable',
      restricted: 'Restricted access',
    } as Record<string, string>,
    classMap: {
      mission_observation: 'Confirmed spaceflight study metadata',
      analog_study: 'Ground analog study metadata',
      simulation: 'Simulation study metadata',
      ground_human_research: 'Ground human research metadata',
      unconfirmed_study_context: 'Study metadata (unconfirmed orbital context)',
      scientific_reference: 'Scientific reference',
    } as Record<string, string>,
    studyMetadataNote: 'Public NASA OSDR study metadata · NOT a personal astronaut measurement',
  },
  es: {
    eyebrow: 'CONTEXTO CIENTÍFICO Y PROCEDENCIA',
    title: 'Consulta científica NASA y CSA',
    subtitle: 'Catálogo verificado de referencias y metadatos de estudios públicos. Separado estrictamente de la telemetría personal, línea base y datos demo.',
    refresh: 'Consultar y verificar fuentes NASA',
    refreshing: 'Consultando…',
    refreshedOk: 'Consulta a fuentes oficiales completada.',
    refreshedFail: 'La verificación detectó errores de indisponibilidad:',
    tabSources: 'Fuentes oficiales',
    tabDomains: 'Peligros, riesgos y programas',
    tabData: 'Datos públicos NASA (OSDR)',
    officialChallenge: 'Referencia científica oficial',
    publicApi: 'API pública NASA (OSDR)',
    openSite: 'Abrir sitio oficial',
    openStudy: 'Abrir registro original en NASA',
    limitations: 'Limitaciones de acceso',
    availability: 'Disponibilidad de datos',
    format: 'Formato',
    units: 'Unidades',
    population: 'Población / contexto',
    license: 'Licencia / términos',
    lastChecked: 'Última verificación',
    lastSuccess: 'Última consulta exitosa',
    neverChecked: 'Sin verificar aún en ejecución',
    noSuccessYet: 'Aún no hay consulta exitosa registrada',
    httpVerifiedBadge: 'Fuente oficial verificada mediante consulta HTTP',
    restrictedDataBadge: 'Acceso restringido a datos',
    hrpRoleTitle: 'NASA HRP (Human Research Program)',
    hrpRoleDesc: 'Proporciona el marco científico de los principales peligros y riesgos del vuelo espacial humano. LÁTIRA utiliza esta clasificación como contexto para organizar y explicar la relevancia de sus indicadores de seguimiento.',
    osdrRoleTitle: 'NASA OSDR (Open Science Data Repository)',
    osdrRoleDesc: 'Proporciona acceso a metadatos de investigaciones científicas públicas sobre salud y vuelos espaciales. LÁTIRA consulta y presenta los registros disponibles para ofrecer contexto científico y facilitar la exploración de investigaciones relacionadas.',
    nonSubstitutionNotice: 'Los recursos NASA complementan el contexto científico de LÁTIRA. Los estudios públicos no representan mediciones personales del astronauta ni sustituyen sus registros individuales de monitoreo.',
    hazardsTitle: 'Cinco peligros de NASA para el vuelo espacial humano',
    hazardsNote: 'Solo contexto científico de misión — no son mediciones personales automáticas.',
    notMeasured: 'Solo contexto · no son mediciones personales',
    hazardHealthLink: 'Relación con el seguimiento de salud',
    hazardIndicators: 'Indicadores de LÁTIRA relacionados',
    risksTitle: 'Dominios de riesgo NASA HRP e indicadores LÁTIRA',
    risksNote: 'Relaciona áreas de investigación con indicadores existentes de LÁTIRA sin alterar umbrales clínicos.',
    mappedTo: 'Indicadores relacionados en LÁTIRA',
    relevanceHeader: 'Explicación científica',
    noDirectSignal: 'Sin indicador directo implementado',
    programsTitle: 'Programas de investigación NASA HRP',
    scientificRelation: 'Relación científica / objetivo',
    programDisclaimer: 'Referencia de investigación: LÁTIRA no tiene acceso a datos privados de participantes ni está conectada a instrumentos de NASA.',
    csaTitle: 'Contexto CSA: Radiación CANS y ciencia en la EEI',
    cansStatus: 'CSA CANS: Solo referencia · NO conectado',
    dataTitle: 'Metadatos públicos verificados de estudios NASA OSDR',
    dataEmpty: 'Aún no hay registros públicos de OSDR almacenados. Una cuenta administradora puede ejecutar la consulta oficial a NASA OSDR.',
    dataUnavailableNotice: 'NASA OSDR no está disponible temporalmente. Se conservan los registros previamente almacenados sin inventar datos.',
    studyId: 'Identificador del estudio',
    studyTitle: 'Título original del estudio',
    organismLabel: 'Organismo o población estudiada',
    missionProgramLabel: 'Programa o misión',
    materialLabel: 'Tipo de muestra o material',
    assayLabel: 'Tecnología o método de análisis',
    obsDate: 'Fecha o periodo disponible',
    queriedAt: 'Fecha de consulta en LÁTIRA',
    classification: 'Clasificación del registro',
    quality: 'Calidad y procedencia',
    origin: 'Endpoint consultado',
    notAvailableInRecord: 'No disponible en el registro de NASA',
    syncReportTitle: 'Resultado de la consulta NASA OSDR',
    fetchedCount: 'Recuperados',
    insertedCount: 'Nuevos guardados',
    updatedCount: 'Actualizados',
    retainedCount: 'Almacenados previamente',
    totalCount: 'Total en caché',
    syncStateMap: {
      new: 'Nuevo registro',
      updated: 'Actualizado',
      previously_stored: 'Almacenado previamente',
    } as Record<string, string>,
    statusMap: {
      reference_only: 'Referencia científica catalogada',
      catalogued: 'Referencia científica catalogada',
      available: 'API pública disponible',
      connected: 'API conectada (consulta real satisfactoria)',
      unavailable: 'Fuente temporalmente no disponible',
      restricted: 'Acceso restringido',
    } as Record<string, string>,
    classMap: {
      mission_observation: 'Estudio en vuelo espacial confirmado',
      analog_study: 'Estudio análogo terrestre',
      simulation: 'Estudio de simulación',
      ground_human_research: 'Investigación humana en Tierra',
      unconfirmed_study_context: 'Estudio público (contexto orbital no confirmado)',
      scientific_reference: 'Referencia científica',
    } as Record<string, string>,
    studyMetadataNote: 'Metadato de estudio público NASA OSDR · NO es medición personal del astronauta',
  },
};

function cleanValue(val: unknown): string | null {
  if (val === null || val === undefined) return null;
  const s = String(val).trim();
  if (!s || s === 'unspecified' || s === 'unspecified_assay' || s === 'unspecified_material') {
    return null;
  }
  return s;
}

export default function NasaScientificPanel({ api, token, lang, role, onRefreshed }: Props) {
  const t = copy[lang];
  const [tab, setTab] = useState<'sources' | 'domains' | 'data'>('sources');
  const [overview, setOverview] = useState<any>(null);
  const [records, setRecords] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [refreshReport, setRefreshReport] = useState<any>(null);

  const load = useCallback(async () => {
    try {
      const [ov, ext] = await Promise.all([
        api('/integrations/nasa', token),
        api('/integrations/nasa/data?limit=20', token),
      ]);
      setOverview(ov);
      setRecords(Array.isArray(ext?.items) ? ext.items : []);
    } catch (e: any) {
      setError(e.message || 'Failed to load NASA/CSA catalog');
    }
  }, [api, token]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRefresh = async () => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await api('/integrations/nasa/refresh', token, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      await load();
      await onRefreshed?.();
      setRefreshReport(res?.refresh_report || null);
      const errEntries = Object.entries(res?.errors || {});
      if (errEntries.length > 0) {
        const errText = errEntries.map(([k, v]) => `${k}: ${v}`).join(' · ');
        setError(`${t.refreshedFail} ${errText}`);
      } else {
        setNotice(t.refreshedOk);
      }
    } catch (e: any) {
      setError(e.message || 'Refresh failed');
    } finally {
      setBusy(false);
    }
  };

  const sources: any[] = overview?.sources || [];
  const domains = overview?.domains || {};
  const indicatorLabels: Record<string, Record<string, string>> = domains.latira_indicator_labels || {};
  const osdrSource = sources.find((s) => s.id === 'nasa-osdr-studies');
  const osdrStatus = String(osdrSource?.verification_status || overview?.summary?.osdr_status || 'available');
  const osdrLastSuccess = osdrSource?.last_successful_at || overview?.summary?.last_successful_at || null;
  const osdrLastError = osdrSource?.last_error || overview?.summary?.osdr_error || null;

  const formatIndicators = (ids: string[] | undefined) => {
    if (!ids || ids.length === 0) return t.noDirectSignal;
    return ids.map((id) => indicatorLabels[id]?.[lang] || id).join(' · ');
  };

  return (
    <section className="panel nasa-panel">
      <div className="panel-head nasa-panel-head">
        <div>
          <span className="eyebrow">{t.eyebrow}</span>
          <h3>{t.title}</h3>
          <p className="muted" style={{ margin: '6px 0 0' }}>{t.subtitle}</p>
        </div>
        {role === 'admin' && (
          <button
            type="button"
            className="small-btn"
            disabled={busy}
            onClick={handleRefresh}
          >
            <RefreshCw size={14} className={busy ? 'spin' : ''} />
            {busy ? t.refreshing : t.refresh}
          </button>
        )}
      </div>

      {/* Clear non-technical explanation of both NASA resources */}
      <div className="nasa-explainer-grid">
        <div className="nasa-explainer-card">
          <b>{t.hrpRoleTitle}</b>
          <p>{t.hrpRoleDesc}</p>
        </div>
        <div className="nasa-explainer-card">
          <b>{t.osdrRoleTitle}</b>
          <p>{t.osdrRoleDesc}</p>
        </div>
      </div>
      <div className="nasa-disclaimer-box" role="note">
        <Info size={15} style={{ flexShrink: 0 }} />
        <span>{t.nonSubstitutionNotice}</span>
      </div>

      {error && (
        <div className="error-banner" style={{ marginTop: 12 }}>
          <span>{error}</span>
          <button type="button" onClick={() => setError('')}>×</button>
        </div>
      )}
      {notice && (
        <div className="nasa-notice" role="status">
          {notice}
        </div>
      )}

      {refreshReport && (
        <div className="nasa-sync-report" role="status">
          <div className="nasa-card-top">
            <b>{t.syncReportTitle}</b>
            <span className={`nasa-badge ${osdrStatus === 'connected' ? 'connected' : osdrStatus === 'unavailable' ? 'unavailable' : 'available'}`}>
              <i />
              {t.statusMap[osdrStatus] || osdrStatus}
            </span>
          </div>
          <div className="nasa-sync-metrics">
            <div><span>{t.fetchedCount}</span><b>{refreshReport.records_fetched ?? 0}</b></div>
            <div><span>{t.insertedCount}</span><b>{refreshReport.records_inserted ?? 0}</b></div>
            <div><span>{t.updatedCount}</span><b>{refreshReport.records_updated ?? 0}</b></div>
            <div><span>{t.retainedCount}</span><b>{refreshReport.previously_stored_retained ?? refreshReport.previously_stored_count ?? 0}</b></div>
            <div><span>{t.totalCount}</span><b>{refreshReport.total_stored_records ?? records.length}</b></div>
            <div><span>{t.lastSuccess}</span><b>{refreshReport.last_successful_at ? new Date(refreshReport.last_successful_at).toLocaleString() : t.noSuccessYet}</b></div>
          </div>
        </div>
      )}

      <div className="metric-mode-toggle" style={{ marginTop: 14 }}>
        <button
          type="button"
          className="small-btn"
          aria-pressed={tab === 'sources'}
          onClick={() => setTab('sources')}
        >
          <BookOpen size={13} />
          {t.tabSources} ({sources.length})
        </button>
        <button
          type="button"
          className="small-btn"
          aria-pressed={tab === 'domains'}
          onClick={() => setTab('domains')}
        >
          <ShieldAlert size={13} />
          {t.tabDomains}
        </button>
        <button
          type="button"
          className="small-btn"
          aria-pressed={tab === 'data'}
          onClick={() => setTab('data')}
        >
          <Database size={13} />
          {t.tabData} ({records.length})
        </button>
      </div>

      {tab === 'sources' && (
        <div className="nasa-source-grid">
          {sources.map((src) => {
            const st = String(src.verification_status || 'reference_only');
            const isConnected = st === 'connected';
            const isRestrictedData = src.access_type === 'restricted_data_request' || st === 'restricted';
            const badgeClass =
              isConnected
                ? 'nasa-badge connected'
                : st === 'available'
                ? 'nasa-badge available'
                : st === 'unavailable'
                ? 'nasa-badge unavailable'
                : st === 'restricted'
                ? 'nasa-badge restricted'
                : 'nasa-badge reference';

            return (
              <article className="nasa-source-card" key={src.id}>
                <div className="nasa-card-top">
                  <span className="tag">
                    {src.endpoint ? t.publicApi : t.officialChallenge}
                  </span>
                  <span className={badgeClass}>
                    <i />
                    {t.statusMap[st] || st}
                  </span>
                </div>
                {(src.http_verified || isRestrictedData) && (
                  <div className="nasa-sub-badges">
                    {src.http_verified && !isConnected && (
                      <span className="nasa-badge verified-http">
                        <CheckCircle2 size={11} />
                        {t.httpVerifiedBadge}
                      </span>
                    )}
                    {isRestrictedData && (
                      <span className="nasa-badge restricted">
                        <i />
                        {t.restrictedDataBadge}
                      </span>
                    )}
                  </div>
                )}
                <h4>{src.name}</h4>
                <small className="nasa-org">{src.organization} · {src.resource_type}</small>
                <p>{lang === 'es' ? src.description_es || src.description : src.description}</p>

                <dl className="nasa-meta">
                  <div>
                    <dt>{t.availability}</dt>
                    <dd>
                      {src.endpoint
                        ? (lang === 'es' ? 'Endpoint JSON público verificable' : 'Verifiable public JSON endpoint')
                        : isRestrictedData
                        ? (lang === 'es' ? 'Catálogo público; datos privados restringidos' : 'Public catalog; private datasets restricted')
                        : (lang === 'es' ? 'Solo referencia / sin API pública' : 'Reference only / no open API')}
                    </dd>
                  </div>
                  <div>
                    <dt>{t.format}</dt>
                    <dd>{src.data_format}</dd>
                  </div>
                  <div>
                    <dt>{t.units}</dt>
                    <dd>{src.units}</dd>
                  </div>
                  <div>
                    <dt>{t.population}</dt>
                    <dd>{src.population}</dd>
                  </div>
                  <div>
                    <dt>{t.license}</dt>
                    <dd>{src.license_or_terms}</dd>
                  </div>
                  <div>
                    <dt>{t.lastChecked}</dt>
                    <dd>{src.last_checked ? new Date(src.last_checked).toLocaleString() : t.neverChecked}</dd>
                  </div>
                  {src.endpoint && (
                    <div>
                      <dt>{t.lastSuccess}</dt>
                      <dd>{src.last_successful_at ? new Date(src.last_successful_at).toLocaleString() : t.noSuccessYet}</dd>
                    </div>
                  )}
                </dl>

                <div className="nasa-limitation">
                  <b>{t.limitations}:</b> {lang === 'es' ? src.limitations_es || src.limitations : src.limitations}
                </div>
                {src.last_error && (
                  <div className="nasa-error-note">{src.last_error}</div>
                )}

                <div className="nasa-card-foot">
                  <a href={src.official_url} target="_blank" rel="noopener noreferrer" className="text-btn">
                    {t.openSite}
                    <ExternalLink size={13} />
                  </a>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {tab === 'domains' && (
        <div className="nasa-domains-stack">
          <div className="nasa-subblock">
            <div className="panel-head">
              <div>
                <h4>{t.hazardsTitle}</h4>
                <p className="muted" style={{ margin: '2px 0 0' }}>{t.hazardsNote}</p>
              </div>
              <a
                href="https://www.nasa.gov/hrp/hazards/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-btn"
              >
                {t.openSite} <ExternalLink size={12} />
              </a>
            </div>
            <div className="nasa-mini-grid">
              {(domains.five_hazards || []).map((hz: any) => (
                <div className="nasa-mini-card" key={hz.id}>
                  <div className="nasa-card-top">
                    <b>{lang === 'es' ? hz.name_es : hz.name_en}</b>
                    <span className="tag">{t.notMeasured}</span>
                  </div>
                  <p>{lang === 'es' ? hz.description_es : hz.description_en}</p>
                  <small>
                    <b>{t.hazardHealthLink}:</b> {lang === 'es' ? hz.latira_note_es : hz.latira_note_en}
                  </small>
                  <small>
                    <b>{t.hazardIndicators}:</b> {formatIndicators(hz.related_latira_indicators)}
                  </small>
                  {hz.official_url && (
                    <a href={hz.official_url} target="_blank" rel="noopener noreferrer" className="text-btn" style={{ marginTop: 4 }}>
                      {hz.official_source_name || t.openSite} <ExternalLink size={12} />
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="nasa-subblock">
            <div className="panel-head">
              <div>
                <h4>{t.risksTitle}</h4>
                <p className="muted" style={{ margin: '2px 0 0' }}>{t.risksNote}</p>
              </div>
              <a
                href="https://www.nasa.gov/hrp/risks/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-btn"
              >
                {t.openSite} <ExternalLink size={12} />
              </a>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{lang === 'es' ? 'Dominio científico' : 'Scientific domain'}</th>
                    <th>{lang === 'es' ? 'Riesgos NASA HRP' : 'NASA HRP risks'}</th>
                    <th>{t.mappedTo}</th>
                    <th>{t.relevanceHeader}</th>
                  </tr>
                </thead>
                <tbody>
                  {(domains.risk_domains || []).map((rk: any) => (
                    <tr key={rk.id}>
                      <td>{lang === 'es' ? rk.domain_es : rk.domain_en}</td>
                      <td className="nasa-wrap-cell">{(rk.nasa_risk_titles || []).join(' · ')}</td>
                      <td className="nasa-wrap-cell">{formatIndicators(rk.related_latira_indicators)}</td>
                      <td className="nasa-wrap-cell">
                        {lang === 'es'
                          ? rk.relevance_explanation_es || rk.summary_es
                          : rk.relevance_explanation_en || rk.summary_en}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="nasa-subblock">
            <div className="panel-head">
              <div>
                <h4>{t.programsTitle}</h4>
                <p className="muted" style={{ margin: '2px 0 0' }}>{t.programDisclaimer}</p>
              </div>
              <a
                href="https://www.nasa.gov/hrp/ongoing-hrp-research/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-btn"
              >
                {t.openSite} <ExternalLink size={12} />
              </a>
            </div>
            <div className="nasa-mini-grid">
              {(domains.ongoing_programs || []).map((prog: any) => (
                <div className="nasa-mini-card" key={prog.id}>
                  <div className="nasa-card-top">
                    <b>{prog.name}</b>
                    <span className="tag">{prog.scientific_domain}</span>
                  </div>
                  <small>{prog.responsible_institution}</small>
                  <p>{lang === 'es' ? prog.description_es : prog.description_en}</p>
                  <small>
                    <b>{t.scientificRelation}:</b>{' '}
                    {lang === 'es' ? prog.research_objective_es : prog.research_objective_en}
                  </small>
                  <small><b>{t.population}:</b> {prog.study_population_or_context}</small>
                  <small><b>{t.availability}:</b> {lang === 'es' ? prog.data_availability_es : prog.data_availability_en}</small>
                  <small><b>{t.limitations}:</b> {lang === 'es' ? prog.access_limitations_es : prog.access_limitations_en}</small>
                  <a href={prog.official_url} target="_blank" rel="noopener noreferrer" className="text-btn" style={{ marginTop: 6 }}>
                    {t.openSite}
                    <ExternalLink size={12} />
                  </a>
                </div>
              ))}
            </div>
          </div>

          {domains.csa_cans && (
            <div className="nasa-subblock">
              <div className="panel-head">
                <h4>{t.csaTitle}</h4>
                <span className="nasa-badge reference"><i />{t.cansStatus}</span>
              </div>
              <div className="nasa-mini-grid">
                <div className="nasa-mini-card">
                  <b>{domains.csa_cans.system_name}</b>
                  <small>{domains.csa_cans.organization} · {domains.csa_cans.article_date}</small>
                  <p>{domains.csa_cans.radiation_type_monitored}. Predecessors: {(domains.csa_cans.predecessor_experiments || []).join(', ')}.</p>
                  <small>{lang === 'es' ? domains.csa_cans.units_note_es : domains.csa_cans.units_note_en}</small>
                  <small>{lang === 'es' ? domains.csa_cans.limitations_es : domains.csa_cans.limitations_en}</small>
                  <a href={domains.csa_cans.official_url} target="_blank" rel="noopener noreferrer" className="text-btn" style={{ marginTop: 6 }}>
                    {t.openSite} <ExternalLink size={12} />
                  </a>
                </div>
                {domains.csa_iss_science && (
                  <div className="nasa-mini-card">
                    <b>{lang === 'es' ? 'Ciencia en la EEI (CSA)' : 'CSA ISS Space Science'}</b>
                    <small>{domains.csa_iss_science.iss_scale}</small>
                    {(domains.csa_iss_science.pillars || []).map((pil: any) => (
                      <p key={pil.id}>
                        <b>{lang === 'es' ? pil.title_es : pil.title_en}:</b>{' '}
                        {lang === 'es' ? pil.summary_es : pil.summary_en}
                      </p>
                    ))}
                    <a href={domains.csa_iss_science.official_url} target="_blank" rel="noopener noreferrer" className="text-btn" style={{ marginTop: 6 }}>
                      {t.openSite} <ExternalLink size={12} />
                    </a>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'data' && (
        <div className="nasa-subblock">
          <div className="panel-head" style={{ flexWrap: 'wrap', gap: 10 }}>
            <div>
              <h4>{t.dataTitle}</h4>
              <small className="nasa-org">
                {t.lastSuccess}: {osdrLastSuccess ? new Date(osdrLastSuccess).toLocaleString() : t.noSuccessYet}
              </small>
            </div>
            <span className={`nasa-badge ${osdrStatus === 'connected' ? 'connected' : osdrStatus === 'unavailable' ? 'unavailable' : 'available'}`}>
              <i />
              {t.statusMap[osdrStatus] || osdrStatus}
            </span>
          </div>

          {osdrStatus === 'unavailable' && (
            <div className="nasa-error-note" style={{ marginTop: 10 }}>
              <b>{t.dataUnavailableNotice}</b>
              {osdrLastError ? ` (${osdrLastError})` : ''}
            </div>
          )}

          {records.length === 0 ? (
            <p className="muted" style={{ marginTop: 12 }}>{t.dataEmpty}</p>
          ) : (
            <div className="nasa-mini-grid">
              {records.map((rec) => {
                const studyId = cleanValue(rec.accession) || cleanValue(rec.variable) || t.notAvailableInRecord;
                const organismVal = cleanValue(rec.organism) || t.notAvailableInRecord;
                const missionProgParts = [cleanValue(rec.flight_program), cleanValue(rec.mission_name)].filter(Boolean);
                const missionProgVal = missionProgParts.length ? missionProgParts.join(' · ') : t.notAvailableInRecord;
                const materialVal = cleanValue(rec.material_type) || t.notAvailableInRecord;
                const assayVal = cleanValue(rec.assay_technology) || t.notAvailableInRecord;
                const obsDateVal = cleanValue(rec.observation_date) || t.notAvailableInRecord;
                const releaseVal = cleanValue(rec.release_date);
                const periodDisplay =
                  releaseVal && obsDateVal !== t.notAvailableInRecord && releaseVal !== obsDateVal
                    ? `${obsDateVal} (${lang === 'es' ? 'publicado' : 'released'} ${releaseVal})`
                    : obsDateVal;
                const syncState = String(rec.sync_state || 'previously_stored');

                return (
                  <article className="nasa-mini-card" key={rec.id || `${rec.source_id}-${rec.accession}`}>
                    <div className="nasa-card-top">
                      <b>{studyId}</b>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        <span className={`tag ${syncState === 'new' ? 'tag-new' : syncState === 'updated' ? 'tag-updated' : ''}`}>
                          {t.syncStateMap[syncState] || t.syncStateMap.previously_stored}
                        </span>
                        <span className="tag">{t.classMap[rec.classification] || rec.classification}</span>
                      </div>
                    </div>
                    <small className="nasa-org">{t.studyMetadataNote}</small>
                    <p><b>{t.studyTitle}:</b> {rec.value}</p>
                    <dl className="nasa-meta">
                      <div><dt>{t.organismLabel}</dt><dd>{organismVal}</dd></div>
                      <div><dt>{t.missionProgramLabel}</dt><dd>{missionProgVal}</dd></div>
                      <div><dt>{t.materialLabel}</dt><dd>{materialVal}</dd></div>
                      <div><dt>{t.assayLabel}</dt><dd>{assayVal}</dd></div>
                      <div><dt>{t.obsDate}</dt><dd>{periodDisplay}</dd></div>
                      <div><dt>{t.queriedAt}</dt><dd>{new Date(rec.queried_at).toLocaleString()}</dd></div>
                      <div><dt>{t.classification}</dt><dd>{t.classMap[rec.classification] || rec.classification}</dd></div>
                      <div><dt>{t.quality}</dt><dd>{rec.quality_indicator}</dd></div>
                      <div><dt>{t.origin}</dt><dd>{rec.origin_url}</dd></div>
                      <div><dt>{t.license}</dt><dd>{rec.license_or_terms}</dd></div>
                    </dl>
                    {(rec.study_url || rec.origin_url) && (
                      <a
                        href={rec.study_url || rec.origin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-btn"
                        style={{ marginTop: 6 }}
                      >
                        {t.openStudy} <ExternalLink size={12} />
                      </a>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

