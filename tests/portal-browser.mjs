/** Real Chrome smoke test; uses only Node built-ins, against a separate test browser. */
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
const base=process.env.PORTAL_PREVIEW_URL || 'http://127.0.0.1:3100';
const debug=process.env.PORTAL_DEBUG_URL || 'http://127.0.0.1:19229';
for(const value of [base,debug])assert.equal(new URL(value).hostname,'127.0.0.1','Smoke test is loopback-only');
const pages=await (await fetch(`${debug}/json/list`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
let next=0;const pending=new Map(),errors=[];
ws.onmessage=({data})=>{const msg=JSON.parse(data);if(msg.id){const p=pending.get(msg.id);if(p){pending.delete(msg.id);msg.error?p.reject(new Error(msg.error.message)):p.resolve(msg.result);}}else if(msg.method==='Runtime.exceptionThrown')errors.push('browser exception');};
function cdp(method,params={}){const id=++next;return new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});}
async function js(expression){const r=await cdp('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error('Browser expression failed; details omitted');return r.result.value;}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
await cdp('Runtime.enable');await cdp('Page.enable');await cdp('Page.bringToFront');
await cdp('Emulation.setDeviceMetricsOverride',{width:1440,height:1260,deviceScaleFactor:1,mobile:false});
await cdp('Page.navigate',{url:base});
for(let i=0;i<50;i++){if(await js("document.querySelectorAll('.service-card').length===6"))break;await wait(100);}
assert.equal(await js("document.querySelectorAll('.service-card').length"),6,'six daily destinations');
assert.equal(await js("[...document.querySelectorAll('.card-main')].every(a=>a.target==='_blank'&&a.href.startsWith('http'))"),true,'configured private links');
assert.equal(await js("/ollama|comfyui|securo|radarr|sonarr/i.test(document.querySelector('main').innerText)"),false,'removed services hidden');
assert.equal(await js("[...document.querySelectorAll('.card-status')].every(e=>e.textContent==='Estado desconhecido')"),true,'honest availability');
await js("document.getElementById('search-trigger').click();document.getElementById('search-input').value='musica';document.getElementById('search-input').dispatchEvent(new Event('input'))");
assert.equal(await js("document.querySelectorAll('.search-result').length"),1,'accent-insensitive search');
await cdp('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await cdp('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
await wait(100);
assert.equal(await js("document.getElementById('search-dialog').open"),false,'keyboard close');
await js("document.querySelector('.favorite-button').click();document.getElementById('favorites-filter').click()");
assert.equal(await js("document.querySelectorAll('.service-card').length"),5,'favorites filter');
await cdp('Page.reload');await wait(350);
assert.equal(await js("document.querySelector('.favorite-button').getAttribute('aria-pressed')"),'false','favorite persists');
await js("document.querySelector('[data-settings]').click();document.getElementById('reset-preferences').click()");
await js("location.hash='admin'");await wait(100);
assert.equal(await js("document.querySelectorAll('.admin-notice').length"),1,'admin warning');
assert.equal(await js("document.querySelectorAll('.service-card').length"),2,'separate administrative links');
await js("location.hash='inicio'");await wait(100);
await wait(3600); // Let the real confirmation toast expire before visual capture.
for (const path of ['/portal.local.json','/manage.py','/../.env','/configs/homepage/services.yaml']) assert.equal((await fetch(base+path)).status,404,'private/source path blocked');
assert.equal((await fetch(base+'/healthz')).status,200,'portal health only');
await js('document.fonts.ready');assert.equal(await js("document.fonts.check('900 40px \"Noctis Display\"')"),true,'local licensed display font loaded');
assert.equal(await js("getComputedStyle(document.body).backgroundColor"),'rgb(7, 7, 7)','NOCTIS palette');
assert.equal(await js("document.getElementById('cathedral-art').closest('[aria-hidden=true]')!==null"),true,'decorative ASCII hidden from screen readers');
const output=process.env.PORTAL_SCREENSHOT_DIR || '/tmp/homelab-noctis-captures';await mkdir(output,{recursive:true});
for(const [label,width,height,mobile]of [['desktop',1440,1260,false],['tablet',820,1180,true],['mobile',390,844,true],['small-mobile',360,800,true],['zoom-reflow',720,1000,true]]){
 await cdp('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile});await wait(100);
 assert.equal(await js('document.documentElement.scrollWidth<=window.innerWidth'),true,`${label}: no horizontal overflow`);
 assert.equal(await js("(()=>{const range=document.createRange();range.selectNodeContents(document.querySelector('.hero h1 em'));return range.getBoundingClientRect().right<=document.querySelector('.hero').getBoundingClientRect().right-8;})()"),true,`${label}: outlined title fully visible`);
 if(label==='mobile'){await js("document.getElementById('sidebar-toggle').click()");assert.equal(await js("document.getElementById('sidebar-toggle').getAttribute('aria-expanded')"),'true','drawer opens');assert.equal(await js("document.getElementById('site-sidebar').inert"),false,'drawer accessible');await js("document.getElementById('sidebar-close').click()");assert.equal(await js("document.getElementById('site-sidebar').inert"),true,'closed drawer is not focusable');}
 if(label==='desktop'||label==='mobile'){
  await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:width-8,y:90,button:'left',clickCount:1});await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:width-8,y:90,button:'left',clickCount:1});
  const result=await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:label==='desktop'});await writeFile(`${output}/${label}.png`,Buffer.from(result.data,'base64'));
 }
}
await cdp('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
assert.equal(await js("getComputedStyle(document.querySelector('.service-card')).transitionDuration"),'0s','reduced motion');
assert.deepEqual(errors,[],'no browser exceptions');
console.log('PASS: real Chrome navigation, search, favorites persistence, private links, Admin, 5 viewports, local font, mobile drawer, reduced motion. Desktop/mobile captures saved.');
ws.close();
