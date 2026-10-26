"use strict";

let db = { articles: [], series: [], reports: [], taxonomy: [], sources: { feeds: [], apis: [], research: [] }, stats: {} };
let shownArticles = 30, shownSources = 24, sourceMode = "all";
const el = (id) => document.getElementById(id);
const dom = (tag, cls, value) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (value !== undefined && value !== null) node.textContent = String(value);
  return node;
};
const clear = (node) => { while (node.firstChild) node.removeChild(node.firstChild); };
const fmtNum = (n) => Number(n || 0).toLocaleString("en-US");
const topic = (id) => (db.taxonomy.find(x => x.id === id) || {}).label || id || "Uncategorized";
const allSources = () => [
  ...(db.sources.feeds || []), ...(db.sources.apis || []), ...(db.sources.datasets || []), ...(db.sources.financials || []), ...(db.sources.research || [])
];
const source = (id) => allSources().find(x => x.id === id);
const link = (href, label, cls = "") => {
  const a = dom("a", cls, label);
  a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
  return a;
};
const DATA_SECTIONS = ["overview", "financials", "adoption", "models", "ecosystem", "sources"];
let currentDataSection = "overview";
function showDataSection(section) {
  currentDataSection = DATA_SECTIONS.includes(section) ? section : "overview";
  for (const name of DATA_SECTIONS) {
    const panel = el("data-" + name), button = el("tab-" + name);
    const selected = name === currentDataSection;
    panel.hidden = !selected;
    panel.classList.toggle("active", selected);
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  }
}
function showView(view, section = null) {
  const active = view === "articles" ? "articles" : "data";
  if (active === "data") showDataSection(section || currentDataSection);
  for (const name of ["data", "articles"]) {
    const visible = name === active;
    el("view-" + name).classList.toggle("active", visible);
    const button = document.querySelector('[data-view="' + name + '"]');
    button.classList.toggle("active", visible);
    if (visible) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  const destination = active === "articles" ? "#articles" : "#data/" + currentDataSection;
  if (location.hash !== destination) history.replaceState(null, "", destination);
}
function routeFromHash() {
  const hash = location.hash.replace(/^#/, "");
  if (hash === "articles") return showView("articles");
  const section = hash.startsWith("data/") ? hash.split("/")[1] : "overview";
  return showView("data", section);
}


function formatMeasure(value, unit) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const decimals = unit === "percent" ? 2 : unit === "USD per 1M tokens" ? 4 : unit === "USD billions" ? 2 : unit === "times" ? 2 : 0;
  return n.toLocaleString("en-US", {maximumFractionDigits: decimals});
}
function renderAnalysisLine(holder, chart) {
  const points = chart.series?.[0]?.points || [];
  if (!points.length) {holder.append(dom("div","empty","No comparable observations yet."));return;}
  const W=560,H=220,l=45,r=14,t=15,b=32;
  const svg=createSvg("svg",{viewBox:"0 0 "+W+" "+H,role:"img",
    "aria-label":chart.title+" values by reporting year"});
  const x=i=>l+(points.length===1?(W-l-r)/2:i*(W-l-r)/(points.length-1));
  // Percentages always retain a genuine 0%-100% axis. No exaggerated growth.
  const y=v=>t+(100-v)*(H-t-b)/100;
  for(const tick of [0,25,50,75,100]){
    const yy=y(tick);
    svg.append(createSvg("line",{x1:l,y1:yy,x2:W-r,y2:yy,class:"line-grid"}));
    svg.append(createSvg("text",{x:l-8,y:yy+4,"text-anchor":"end",class:"line-axis"},tick+"%"));
  }
  const path=points.map((p,i)=>(i===0?"M":"L")+x(i)+","+y(Number(p.value))).join(" ");
  svg.append(createSvg("path",{d:path,class:"line-path"}));
  for(const [i,p] of points.entries()){
    const dot=createSvg("circle",{cx:x(i),cy:y(Number(p.value)),r:5,class:"line-dot"});
    dot.append(createSvg("title",{},p.period+": "+formatMeasure(p.value,"percent")+"%"));
    svg.append(dot);
    svg.append(createSvg("text",{x:x(i),y:H-9,"text-anchor":"middle",class:"line-axis"},p.period));
  }
  holder.append(svg);
}
function renderAnalysisBars(holder, chart) {
  const points=chart.points || [];
  if(!points.length){holder.append(dom("div","empty","No data available for this breakdown."));return;}
  const maximum=chart.unit==="percent"?100:Math.max(1,...points.map(p=>Number(p.value)||0));
  const stack=dom("div","vbar-stack");
  for(const row of points){
    const item=dom("div","hbar");
    const label=row.source_url ? link(row.source_url,row.label,"hbar-label") : dom("span","hbar-label",row.label);
    label.title=row.label+(row.n?" ("+row.n+" selected listed models)":"");
    const track=dom("div","hbar-track"),fill=dom("div","hbar-fill");
    fill.style.width=Math.max(0,Math.min(100,(Number(row.value)||0)/maximum*100))+"%";
    track.append(fill);
    const value=dom("span","hbar-value",formatMeasure(row.value,chart.unit));
    value.title=row.n?"Median of "+row.n+" sampled prices":"";
    item.append(label,track,value);
    stack.append(item);
  }
  holder.append(stack);
}
// Explicit research-domain mapping prevents a chart of model pricing from
// being mistaken for company finances, or publication coverage for adoption.
function analysisCategory(id) {
  if (id.startsWith("sec_")) return "finance-charts";
  if (id === "eurostat_adoption" || id === "survey_adoption" ||
      id === "regional_survey_adoption") return "adoption-charts";
  if (id.startsWith("price_")) return "model-charts";
  return "ecosystem-charts";
}
function renderAnalysis() {
  const analysis = db.analysis || {};
  const cards = el("analysis-cards"), findings = el("analysis-findings"), gaps = el("analysis-gaps");
  const grids = ["finance-charts", "adoption-charts", "model-charts", "ecosystem-charts"];
  [cards, findings, gaps, ...grids.map(el)].forEach(clear);
  if (!analysis.charts?.length) {
    cards.append(dom("div", "empty", "Analysis has not been generated from the stored evidence yet."));
    return;
  }
  el("analysis-link").href = "https://github.com/BestNathan/ai-industry-research/blob/main/data/reports/analysis/" + analysis.report_date + ".md";
  for (const card of analysis.cards || []) {
    const box = dom("article", "analysis-card");
    box.append(dom("div", "analysis-card-label", card.label));
    box.append(dom("div", "analysis-card-value",
      formatMeasure(card.value, card.suffix === "%" ? "percent" : "count") + card.suffix));
    box.append(dom("div", "analysis-card-period", card.period + " · " + card.delta));
    box.append(dom("div", "analysis-card-detail", card.description));
    cards.append(box);
  }
  for (const chart of analysis.charts || []) {
    const wrap = dom("article", "analysis-chart"), heading = dom("div", "analysis-chart-header");
    const name = dom("div");
    name.append(dom("h4", "", chart.title),
                dom("div", "analysis-chart-sub", chart.scope || chart.unit));
    heading.append(name);
    wrap.append(heading);
    const plot = dom("div", "analysis-chart-plot");
    if (chart.type === "line") renderAnalysisLine(plot, chart);
    else renderAnalysisBars(plot, chart);
    wrap.append(plot);
    const foot = dom("div", "analysis-chart-foot");
    foot.append(dom("span", "", chart.caveat + " "));
    if (chart.source_url) foot.append(link(chart.source_url, "View original source ↗"));
    wrap.append(foot);
    el(analysisCategory(chart.id)).append(wrap);
  }
  for (const gridId of grids) {
    if (!el(gridId).children.length)
      el(gridId).append(dom("div", "empty", "No comparable public observations collected for this category yet."));
  }
  for (const f of analysis.findings || []) {
    const row = dom("article", "insight-row");
    row.append(dom("div", "insight-eyebrow", f.kind.replaceAll("_", " ")));
    row.append(dom("strong", "", f.title), dom("p", "", f.text));
    for (const id of f.source_ids || []) {
      const item = source(id);
      if (item?.homepage || item?.url)
        row.append(link(item.homepage || item.url, "Evidence: " + item.title + " ↗"));
      else if (f.source_url && id === "sec_edgar")
        row.append(link(f.source_url, "SEC filing evidence ↗"));
    }
    findings.append(row);
  }
  for (const gap of analysis.coverage_gaps || []) {
    const row = dom("article", "insight-row");
    row.append(dom("strong", "", gap.title), dom("p", "", gap.reason));
    gaps.append(row);
  }
  el("analysis-note").textContent = analysis.research_note || "";
}

function renderStats() {
  const labels = [
    ["Collected articles", db.stats.articles],
    ["Metric observations", db.stats.observations],
    ["Automated sources", db.stats.sources_automated],
    ["Research sources", db.stats.sources_reference],
  ];
  clear(el("stats"));
  for (const [label, number] of labels) {
    const box = dom("div", "stat");
    box.append(dom("span", "stat-label", label), dom("strong", "", fmtNum(number)));
    el("stats").append(box);
  }
  const date = db.source_health?.generated_at;
  el("updated-label").textContent = date ? "· LAST COLLECTED " + date.slice(0, 10) : "· AWAITING FIRST RUN";
}

function renderHealth() {
  const holder = el("health"); clear(holder);
  const h = db.source_health || {};
  if (!h.sources?.length) {
    holder.append(dom("div", "empty", "No source collection recorded. Run the scheduled workflow or trigger it manually.")); return;
  }
  const q=db.quality||{};
  const counts=q.sources||{};
  const summary=dom("p","minor",
    (h.successful_sources||0)+" healthy · "+(h.failed_sources||0)+" failed · "+
    (h.skipped_sources||0)+" need setup · "+(counts.stale||0)+" stale · "+h.date);
  holder.append(summary);
  const priority={failed:0,skipped_config:1,not_collected:2,ok:3};
  for (const row of [...h.sources].sort((a,b) =>
        (priority[a.status]??4)-(priority[b.status]??4)).slice(0, 14)) {
    const wrap = dom("div", "health-item"), left = dom("div", "health-left");
    left.append(dom("span", "health-name", source(row.source_id)?.title || row.source_id));
    const healthText = row.status === "ok" ? fmtNum(row.records) + " records · latest fetch OK"
      : row.status === "skipped_config" ? row.reason || "Configure SEC_USER_AGENT"
      : (row.error || "Collection failed") + (row.last_success_at ? " · last success " + row.last_success_at.slice(0,10) : " · no previous success");
    left.append(dom("span", "health-meta", healthText));
    wrap.append(left, dom("span", "pill " + row.status, row.status)); holder.append(wrap);
  }
}

function numberDisplay(value, unit) {
  if (!Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  if (unit?.startsWith("USD")) return "$" + n.toLocaleString("en-US", {maximumFractionDigits: 4});
  return n.toLocaleString("en-US", {maximumFractionDigits: n < 1 ? 5 : 0});
}
function seriesName(s) {
  const who = s.entity_id.startsWith("owid:ai_adoption:") ? "McKinsey survey: " + s.geography :
    s.entity_id.startsWith("eurostat:ai_adoption:") ? "Eurostat: " + s.geography :
    s.entity_id.replace(/^(github:|huggingface:|openrouter:)/, "");
  return who + " · " +
    s.metric_id.replace(/^github\./, "").replace(/^huggingface\./, "").replace(/^openrouter\./, "").replaceAll("_", " ");
}
function createSvg(tag, attributes = {}, text = null) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k,v] of Object.entries(attributes)) node.setAttribute(k, String(v));
  if (text !== null) node.textContent = text;
  return node;
}
function renderChart(index) {
  const s = db.series[index];
  const holder = el("chart-area"); clear(holder);
  if (!s?.points?.length) {
    holder.append(dom("div", "empty", "No series data is available yet.")); return;
  }
  const points = s.points.filter(p => Number.isFinite(Number(p.value)));
  if (!points.length) return;
  const W = 900, H = 285, l = 75, r = 20, t = 20, b = 40;
  const values = points.map(p => Number(p.value));
  let min = Math.min(...values), max = Math.max(...values);
  const pad = Math.max((max - min) * .15, max * .025, .001);
  min = Math.max(0, min - pad); max += pad;
  const x = i => l + (points.length === 1 ? (W - l - r) / 2 : i * (W - l - r) / (points.length - 1));
  const y = v => t + (max - v) * (H - t - b) / (max - min || 1);
  const svg = createSvg("svg", {viewBox: "0 0 " + W + " " + H, role:"img",
                                "aria-label":"Time series for " + seriesName(s)});
  svg.classList.add("line-chart");
  for (let j=0; j<4; j++) {
    const value = min + (max - min) * j / 3, py = y(value);
    svg.append(createSvg("line", {x1:l,y1:py,x2:W-r,y2:py,class:"line-grid"}));
    svg.append(createSvg("text", {x:l-10,y:py+4,"text-anchor":"end",class:"line-axis"}, numberDisplay(value, s.unit)));
  }
  const d = points.map((p,i) => (i === 0 ? "M" : "L") + x(i).toFixed(1) + "," + y(Number(p.value)).toFixed(1)).join(" ");
  svg.append(createSvg("path", {d,class:"line-path"}));
  for (const [i,p] of points.entries()) {
    const dot = createSvg("circle", {cx:x(i),cy:y(Number(p.value)),r:points.length<8?5:3,class:"line-dot"});
    dot.append(createSvg("title", {}, p.date + ": " + numberDisplay(p.value,s.unit) + " " + s.unit));
    svg.append(dot);
  }
  svg.append(createSvg("text", {x:l,y:H-7,class:"line-axis"}, points[0].date));
  svg.append(createSvg("text", {x:W-r,y:H-7,"text-anchor":"end",class:"line-axis"}, points.at(-1).date));
  holder.append(svg);
  const note = el("chart-note");
  clear(note);
  const period = s.period_type === "calendar_year"
    ? "Reporting years are the survey years, not the dates this data was downloaded."
    : "These are collection-day API snapshots, not audited market-wide measurements.";
  note.append(dom("span", "", s.methodology + ". Unit: " + s.unit + ". " + period + " "));
  const original = source(s.source_id);
  if (original?.homepage) note.append(link(original.homepage, "Original source ↗"));
  if (points.length === 1) note.append(dom("span", "", " One observation is not a trend."));
}
function renderSeries() {
  const select = el("metric-select"); clear(select);
  if (!db.series.length) {
    select.append(dom("option", "", "Awaiting first metric snapshot")); return;
  }
  db.series.forEach((s, i) => {
    const option = dom("option", "", seriesName(s));
    option.value = i; select.append(option);
  });
  select.addEventListener("change", () => renderChart(Number(select.value)));
  renderChart(0);
}

function renderReports() {
  const holder = el("reports"); clear(holder);
  if (!db.reports.length) {
    holder.append(dom("div", "empty", "No daily reports published yet.")); return;
  }
  for (const r of db.reports.slice(0, 9)) {
    const card = dom("article", "report");
    card.append(dom("div", "report-date", r.date));
    card.append(dom("strong", "", fmtNum(r.new_articles) + " new articles"));
    card.append(dom("p", "", fmtNum(r.metric_observations) + " normalized metric snapshots"));
    card.append(dom("p", "", r.sources_ok + " sources healthy · " + r.sources_failed + " failures"));
    card.append(link("https://github.com/BestNathan/ai-industry-research/blob/main/data/reports/daily/" + r.date + ".md", "View daily report ↗"));
    holder.append(card);
  }
}

function renderSources() {
  const holder = el("source-list"); clear(holder);
  const items = allSources().filter(x => sourceMode === "all" || x.mode === sourceMode);
  el("source-count").textContent = items.length + " registered";
  for (const row of items.slice(0, shownSources)) {
    const card = dom("article", "source-card"), top = dom("div", "source-top");
    top.append(link(row.homepage || row.url, row.title, "source-title"),
               dom("span", "pill", row.mode === "reference" ? "TRACKED" : row.mode.toUpperCase()));
    card.append(top, dom("p", "", row.notes || "Source catalog entry"));
    const meta = dom("div", "source-meta");
    meta.append(dom("span", "", topic(row.category)), dom("span", "", row.access || ""));
    card.append(meta); holder.append(card);
  }
  el("source-more").hidden = shownSources >= items.length;
}
function renderFilters() {
  const cats = el("article-category"), sources = el("article-source");
  for (const c of db.taxonomy) {
    const opt = dom("option", "", c.label); opt.value = c.id; cats.append(opt);
  }
  const used = [...new Set(db.articles.map(a => a.source_id))].sort();
  for (const id of used) {
    const opt = dom("option", "", source(id)?.title || id); opt.value = id; sources.append(opt);
  }
}

function renderArticles() {
  const holder = el("article-list"); clear(holder);
  const search = el("article-search").value.trim().toLowerCase(),
        category = el("article-category").value, publisher = el("article-source").value,
        scope = el("article-scope").value;
  const selected = db.articles.filter(a => {
    if (scope === "core" && source(a.source_id)?.priority !== "core") return false;
    if (category !== "all" && a.primary_category !== category && !(a.tags || []).includes(category)) return false;
    if (publisher !== "all" && a.source_id !== publisher) return false;
    return !search || [a.title,a.summary,a.publisher,(a.tags || []).join(" ")].join(" ").toLowerCase().includes(search);
  });
  el("article-count").textContent = fmtNum(selected.length) + " matching articles";
  for (const a of selected.slice(0, shownArticles)) {
    const item = dom("article", "article"), side = dom("div"), content = dom("div", "article-main");
    side.append(dom("div", "article-source", a.publisher || source(a.source_id)?.title || a.source_id));
    side.append(dom("div", "article-date", (a.published_at || a.discovered_at || "").slice(0,10)));
    content.append(link(a.url, a.title));
    if (a.summary) content.append(dom("p", "", a.summary));
    const tags = dom("div", "tags");
    for (const tag of (a.tags || []).slice(0,4)) tags.append(dom("span", "tag", topic(tag)));
    content.append(tags);
    content.append(dom("div", "article-meta", (a.official_feed ? "Official feed" : "Unofficial indexed feed") + " · First captured " + a.discovered_at?.slice(0,10) + " · Original publication ↗"));
    item.append(side, content); holder.append(item);
  }
  if (!selected.length) holder.append(dom("div", "empty", "No articles match the current filters. Try a broader query."));
  el("article-more").hidden = shownArticles >= selected.length;
}

async function start() {
  for (const button of document.querySelectorAll(".nav-button"))
    button.addEventListener("click", () => showView(button.dataset.view));
  for (const button of document.querySelectorAll("[data-data-tab]")) {
    button.addEventListener("click", () => showView("data", button.dataset.dataTab));
    button.addEventListener("keydown", (event) => {
      const index = DATA_SECTIONS.indexOf(button.dataset.dataTab);
      let next;
      if (event.key === "ArrowRight") next = (index + 1) % DATA_SECTIONS.length;
      else if (event.key === "ArrowLeft") next = (index - 1 + DATA_SECTIONS.length) % DATA_SECTIONS.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = DATA_SECTIONS.length - 1;
      else return;
      event.preventDefault();
      showView("data", DATA_SECTIONS[next]);
      el("tab-" + DATA_SECTIONS[next]).focus();
    });
  }
  for (const button of document.querySelectorAll("[data-open-section]"))
    button.addEventListener("click", () => showView("data", button.dataset.openSection));
  window.addEventListener("hashchange", routeFromHash);
  routeFromHash();
  try {
    const response = await fetch("./data/dashboard.json", {cache:"no-cache"});
    if (!response.ok) throw Error("HTTP " + response.status);
    db = await response.json();
  } catch (error) {
    el("updated-label").textContent = "· DATA COULD NOT BE LOADED";
    el("health").textContent = "Failed to load dashboard data: " + error.message;
    return;
  }
  renderStats(); renderAnalysis(); renderFinance(); renderHealth(); renderSeries(); renderReports(); renderFilters(); renderSources(); renderArticles();
  el("source-filter").addEventListener("change", (e) => {sourceMode = e.target.value;shownSources=24;renderSources();});
  el("source-more").addEventListener("click", () => {shownSources += 24;renderSources();});
  for (const id of ["article-search","article-scope","article-category","article-source"])
    el(id).addEventListener("input", () => {shownArticles=30;renderArticles();});
  el("article-more").addEventListener("click", () => {shownArticles+=30;renderArticles();});
}
document.addEventListener("DOMContentLoaded", start);
