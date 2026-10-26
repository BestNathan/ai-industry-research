// Actual browser smoke suite. No npm packages: Node 22 WebSocket + Chrome DevTools Protocol.
import {createServer} from "node:http";
import {spawn,spawnSync} from "node:child_process";
import {mkdtemp,readFile,rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {resolve,join,relative,extname} from "node:path";
import {setTimeout as pause} from "node:timers/promises";

const root=resolve("_site");
const mime={".html":"text/html",".css":"text/css",".js":"text/javascript",".json":"application/json"};
const server=createServer(async(req,res)=>{
  const url=new URL(req.url,"http://localhost");
  const file=resolve(root,"."+decodeURIComponent(url.pathname==="/"?"/index.html":url.pathname));
  if(relative(root,file).startsWith("..")){res.writeHead(403).end();return;}
  try{const bytes=await readFile(file);res.writeHead(200,{"content-type":mime[extname(file)]||"text/plain"});res.end(bytes);}
  catch{res.writeHead(404).end("Not found");}
});
let chrome,dir,socket;
const errors=[];
const assert=(value,message)=>{if(!value)throw Error(message);};
const chromePath=()=>{
  for(const name of ["google-chrome","google-chrome-stable","chromium","chromium-browser"]){
    const r=spawnSync("which",[name],{encoding:"utf8"});
    if(r.status===0&&r.stdout.trim())return r.stdout.trim();
  }
  throw Error("Chrome/Chromium unavailable on CI host");
};
async function connect(uri){
  return new Promise((resolve,reject)=>{
    const sock=new WebSocket(uri);
    sock.addEventListener("open",()=>resolve(sock),{once:true});
    sock.addEventListener("error",e=>reject(Error("CDP WebSocket failed "+String(e))),{once:true});
  });
}
async function main(){
  await new Promise((resolve,reject)=>{server.once("error",reject);server.listen(0,"127.0.0.1",resolve);});
  dir=await mkdtemp(join(tmpdir(),"industry-chrome-"));
  const binary=chromePath();
  console.log("Launching browser", binary);
  let browserLogs="";
  chrome=spawn(binary,["--headless=new","--no-sandbox","--disable-gpu",
    "--disable-dev-shm-usage","--no-first-run","--disable-background-networking",
    "--user-data-dir="+dir,"--remote-debugging-port=0",
    "--remote-allow-origins=*","about:blank"],{stdio:["ignore","pipe","pipe"]});
  chrome.stdout.on("data",b=>{browserLogs+=(String(b)).slice(-8000);});
  chrome.stderr.on("data",b=>{browserLogs+=(String(b)).slice(-8000);});
  let port;
  for(let i=0;i<100;i++){
    try{port=Number((await readFile(join(dir,"DevToolsActivePort"),"utf8")).split("\n")[0]);break;}
    catch{await pause(100);}
  }
  assert(port,"Chrome DevToolsActivePort not available; exit="+chrome.exitCode+"; logs="+browserLogs.slice(-5000));
  const pages=await(await fetch("http://127.0.0.1:"+port+"/json/list")).json();
  const page=pages.find(p=>p.type==="page");
  assert(page?.webSocketDebuggerUrl,"Chrome CDP target not found");
  socket=await connect(page.webSocketDebuggerUrl);
  let id=0;
  const calls=new Map();
  socket.addEventListener("message",event=>{
    const msg=JSON.parse(event.data);
    if(msg.method==="Runtime.exceptionThrown")errors.push(msg.params?.exceptionDetails?.exception?.description||msg.params?.exceptionDetails?.text||"Unknown error");
    if(msg.id&&calls.has(msg.id)){
      const [ok,bad]=calls.get(msg.id);calls.delete(msg.id);
      msg.error?bad(Error(JSON.stringify(msg.error))):ok(msg.result);
    }
  });
  const send=(method,params={})=>new Promise((ok,bad)=>{
    const request=++id;calls.set(request,[ok,bad]);
    socket.send(JSON.stringify({id:request,method,params}));
  });
  const evaluate=async expression=>{
    const r=await send("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true});
    if(r.exceptionDetails)throw Error("Browser exception: "+(r.exceptionDetails.exception?.description||r.exceptionDetails.text));
    return r.result.value;
  };
  await send("Runtime.enable");await send("Page.enable");
  await send("Page.navigate",{url:"http://127.0.0.1:"+server.address().port+"/"});
  let result;
  for(let i=0;i<100;i++){
    await pause(120);
    result=await evaluate("({loaded:document.querySelector('#updated-label')?.textContent?.includes('LAST COLLECTED'),"+
      "alert:document.querySelector('#runtime-alert')?.textContent,"+
      "cards:document.querySelectorAll('#analysis-cards .analysis-card').length,"+
      "finance:document.querySelectorAll('#finance-table-body tr.issuer-row').length,"+
      "articles:document.querySelectorAll('#article-list article.article').length,"+
      "sources:document.querySelectorAll('#source-list .source-card').length})");
    if(result.loaded&&(result.cards||result.alert||result.articles))break;
  }
  console.log("Browser results:",JSON.stringify(result));
  assert(result.loaded,"Dashboard JSON did not load");
  assert(!result.alert,"Client errors: "+result.alert);
  assert(result.cards>=2,"Missing overview KPI cards");
  assert(result.finance===6,"Expected six issuer financial rows");
  assert(result.articles>0,"Articles list never rendered");
  assert(result.sources>0,"Sources list never rendered");
  const finance=await evaluate("(document.getElementById('tab-financials').click(),"+
    "{active:document.getElementById('data-financials').classList.contains('active'),"+
    "url:document.querySelector('#finance-table-body a.finance-amount-link')?.href,hash:location.hash})");
  assert(finance.active&&finance.hash==="#data/financials","Financial tab failed to activate");
  assert(finance.url?.startsWith("https://www.sec.gov/"),"SEC evidence link invalid");
  const history=await evaluate("(document.querySelector('#finance-table-body .issuer-pick').click(),"+
    "{points:document.querySelectorAll('#finance-history circle.finance-line-dot').length,"+
    "source:document.querySelector('#finance-history-records a')?.href})");
  assert(history.points>=2&&history.source?.startsWith("https://www.sec.gov/"),"Issuer history click failed");
  const articles=await evaluate("(document.querySelector('[data-view=articles]').click(),"+
    "{shown:document.getElementById('view-articles').classList.contains('active'),"+
    "count:document.querySelectorAll('#article-list article.article').length,"+
    "source:document.querySelector('#article-list article.article a')?.href,hash:location.hash})");
  assert(articles.shown&&articles.count>0&&articles.hash==="#articles","Articles button failed");
  assert(articles.source?.startsWith("https://"),"Article source links absent");
  const sources=await evaluate("(document.querySelector('[data-view=data]').click(),"+
    "document.getElementById('tab-sources').click(),"+
    "{shown:document.getElementById('data-sources').classList.contains('active'),"+
    "rows:document.querySelectorAll('#source-list .source-card').length})");
  assert(sources.shown&&sources.rows>0,"Sources tab unusable");
  assert(!errors.length,"Uncaught browser JS errors: "+errors.join("; "));
  console.log("PASS: Chrome rendered all Data/Articles sections and interactive source links.");
}
try{await main();}
catch(error){console.error("BROWSER SMOKE FAILURE",error.stack||error);process.exitCode=1;}
finally{try{socket?.close();}catch{}try{chrome?.kill("SIGKILL");}catch{}try{server.close();}catch{}if(dir)try{await rm(dir,{recursive:true,force:true});}catch{}}
