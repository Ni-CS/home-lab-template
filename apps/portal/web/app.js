import { GROUPS, ICONS, validateConfig, mergeConfig, destinations, matches } from './model.js';
const paths = {
 home:'M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',
 aperture:'M14.3 3.3 3.7 9.4M20.8 7.3H8.5M21.1 14.3 15 3.7M14.3 20.7l6.1-10.6M3.2 16.7h12.3M2.9 9.7 9 20.3',
 music:'M9 18V5l12-2v13M9 7l12-2M9 18a3 3 0 1 1-3-3c1.7 0 3 1.3 3 3Zm12-2a3 3 0 1 1-3-3c1.7 0 3 1.3 3 3Z',
 play:'m9 5 11 7-11 7ZM4 5v14',folder:'M3 7V5a1 1 0 0 1 1-1h5l2 3h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z',
 book:'M12 6c-3-3-7-3-10-2v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-3-1-7-1-10 2Zm0 0v15',
 notebook:'M5 3h14a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H5ZM3 7h4m-4 5h4m-4 5h4m4-10h5m-5 5h5',
 activity:'M3 12h4l3-8 4 16 3-8h4',chart:'M4 3v17h17M8 15v-4m5 4V7m5 8v-5',
 grid:'M3 3h7v7H3Zm11 0h7v7h-7ZM3 14h7v7H3Zm11 0h7v7h-7Z',
 shield:'M12 3 3 6v6c0 5 9 9 9 9s9-4 9-9V6Zm-5 9 3 3 7-7',network:'M9 3h6v5H9Zm3 5v5m-7 3v-3h14v3M2 17h6v5H2Zm14 0h6v5h-6Z',
 sliders:'M4 21v-7m0-4V3m8 18v-9m0-4V3m8 18v-3m0-4V3M1 14h6m2-6h6m2 10h6',
 lock:'M5 11h14v10H5Zm3 0V7a4 4 0 0 1 8 0v4',search:'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
 star:'m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9Z',
 compass:'m16 8-3 5-5 3 3-5Zm6 4a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
 'arrow-up-right':'M7 17 17 7M7 7h10v10','arrow-right':'M4 12h16m-6-6 6 6-6 6',x:'M6 6l12 12M6 18 18 6',check:'m5 12 4 4L19 6',scan:'M3 8V4a1 1 0 0 1 1-1h4m8 0h4a1 1 0 0 1 1 1v4m0 8v4a1 1 0 0 1-1 1h-4m-8 0H4a1 1 0 0 1-1-1v-4M7 12h10'
};
function icon(name) { const svg = document.createElementNS('http://www.w3.org/2000/svg','svg'); svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('fill','none'); svg.setAttribute('stroke','currentColor'); svg.setAttribute('stroke-linecap','round'); svg.setAttribute('stroke-linejoin','round'); svg.setAttribute('aria-hidden','true'); const path=document.createElementNS(svg.namespaceURI,'path'); path.setAttribute('d',paths[name] || paths.grid); svg.append(path); if(name==='aperture'){const c=document.createElementNS(svg.namespaceURI,'circle');c.setAttribute('cx','12');c.setAttribute('cy','12');c.setAttribute('r','10');svg.append(c);} return svg; }
function icons(root=document) { root.querySelectorAll('[data-icon]').forEach(el => el.replaceChildren(icon(el.dataset.icon))); }
function element(tag, cls, text) { const e=document.createElement(tag); if(cls)e.className=cls; if(text)e.textContent=text; return e; }
const $=id=>document.getElementById(id), storageKey='homelab.portal.v1';
let services=[], server={}, local={}, config={}, cards=[], group='Início', onlyFavorites=false, activeResult=0;
function notify(message) { $('toast').textContent=message; $('toast').hidden=false; setTimeout(()=>$('toast').hidden=true,3500); }
function saveLocal(next) { validateConfig(mergeConfig(server,next),services); try{localStorage.setItem(storageKey,JSON.stringify(next));}catch{notify('O navegador não permitiu salvar. Preferências válidas apenas nesta sessão.');} local=next; update(); }
function destinationLink(s, cls) { const a=element('a',cls); a.href=s.url || '#configurar'; if(s.url) {a.target='_blank';a.rel='noopener noreferrer';} else a.addEventListener('click',e=>{e.preventDefault();openSettings();notify(`Configure o endereço de ${s.title}.`);}); return a; }
function toggleFavorite(s) { const next=structuredClone(local); next.services ||= {}; next.services[s.id]={...next.services[s.id],favorite:!s.favorite}; saveLocal(next); }
function createCard(s) {
 const card=element('article',`service-card card-${s.art}`);card.dataset.service=s.id;
 const top=element('div','card-top'), app=element('span','app-icon');app.append(icon(s.icon));
 const favorite=element('button','favorite-button');favorite.type='button';favorite.setAttribute('aria-label',`Favoritar ${s.title}`);favorite.setAttribute('aria-pressed',String(s.favorite));favorite.append(icon('star'));favorite.addEventListener('click',()=>toggleFavorite(s));top.append(app,favorite);
 const art=element('div','card-art');art.setAttribute('aria-hidden','true');const arts={memories:'memory-stack',sound:'vinyl',cinema:'cinema-lines',files:'folder-art',reading:'book-art',notes:'notes-art'};if(arts[s.art])art.append(element('div',arts[s.art]));if(s.art==='memories')art.append(element('div','memory-sun'));
 const link=destinationLink(s,'card-main');link.append(element('span','eyebrow',s.eyebrow),element('h3','',s.title),element('p','',s.description));
 const status=element('span','card-status');status.append(element('i'),document.createTextNode(s.url?'Estado desconhecido':'Configurar endereço'));const arrow=element('span','card-arrow');arrow.append(icon('arrow-up-right'));link.append(status,arrow);card.append(art,link,top);return card;
}
function systemCard(s) { const a=destinationLink(s,'system-card'),i=element('span','app-icon');i.append(icon(s.icon));const t=element('div');t.append(element('h3','',s.title),element('p','',s.url?'Disponibilidade desconhecida':'Configurar endereço'));a.append(i,t,icon('arrow-up-right'));return a; }
function update() {
 config=validateConfig(mergeConfig(server,local),services);cards=destinations(services,config);document.title=`${config.title} · Seu espaço`;
 document.querySelector('.brand-text').firstChild.textContent=config.title.toLowerCase();
 $('breadcrumb-title').textContent=group==='Início'?'Visão geral':group;
 document.querySelector('.hero').hidden=group!=='Início';
 $('section-kicker').textContent=group==='Início'?'O QUE IMPORTA, POR PERTO':({Mídia:'DÊ PLAY NO SEU TEMPO',Biblioteca:'HISTÓRIAS, MEMÓRIAS E IDEIAS',Sistema:'NOS BASTIDORES',Admin:'ATALHOS ADMINISTRATIVOS'})[group];
 $('section-title').replaceChildren(document.createTextNode(group==='Início'?'Seus essenciais':group),element('span','','.'));
 document.querySelectorAll('.nav-item').forEach(a=>{const active=a.dataset.group===group;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
 const visible=cards.filter(s=>(group==='Início'?['Mídia','Biblioteca'].includes(s.group):s.group===group)&&(!onlyFavorites||s.favorite));
 $('service-grid').replaceChildren(...visible.map(createCard));
 if(group==='Admin'){const note=element('p','admin-notice','Somente atalhos. Cada serviço deve exigir sua própria autenticação. Este portal não executa ações administrativas e não controla containers.');$('service-grid').prepend(note);}
 $('empty').hidden=visible.length>0;
 $('system-section').hidden=group!=='Início';$('system-grid').replaceChildren(...cards.filter(s=>s.group==='Sistema').map(systemCard));
 $('favorites-filter').setAttribute('aria-pressed',String(onlyFavorites));icons();
}
function renderSearch() {const result=cards.filter(s=>matches(s,$('search-input').value));activeResult=Math.max(0,Math.min(activeResult,result.length-1));$('search-results').replaceChildren(...result.map((s,i)=>{const a=destinationLink(s,'search-result');a.dataset.active=String(i===activeResult);a.append(icon(s.icon));const t=element('div');t.append(element('strong','',s.title),element('small','',`${s.group} · ${s.url?'Estado desconhecido':'Configurar endereço'}`));a.append(t,icon('arrow-up-right'));return a;}));if(!result.length)$('search-results').append(element('p','empty','Nenhum destino encontrado. Tente música, arquivos ou sistema.'));}
function openSearch(){activeResult=0;$('search-input').value='';renderSearch();$('search-dialog').showModal();$('search-input').focus();}
function field(label,type,value,id){const l=element('label','',label),input=element('input');input.type=type;input.value=value??'';input.id=id;l.append(input);return l;}
function openSettings(){ $('portal-title').value=config.title;$('base-url').value=config.base_url;$('settings-error').textContent='';const rows=services.map((s,i)=>{const custom=config.services[s.id]||{},d=element('details');d.append(element('summary','',custom.title||s.title));const cols=element('div','settings-row');cols.append(field('Título','text',custom.title||s.title,`title-${s.id}`),field('Ordem','number',custom.order??i,`order-${s.id}`));d.append(cols,field('URL específica (opcional)','url',custom.url||'',`url-${s.id}`));const label=element('label','','Ícone'),select=element('select');select.id=`icon-${s.id}`;for(const name of ICONS){const o=element('option','',name);o.value=name;o.selected=name===(custom.icon||s.icon);select.append(o);}label.append(select);d.append(label);for(const [key,text] of [['enabled','Exibir no portal'],['favorite','Favorito']]){const label=element('label','settings-checkbox'),input=element('input');input.type='checkbox';input.id=`${key}-${s.id}`;input.checked=custom[key]??(key==='enabled'?true:s.favorite);label.append(input,document.createTextNode(text));d.append(label);}return d;});$('service-settings').replaceChildren(...rows);$('settings-dialog').showModal();$('portal-title').focus();}
$('settings-form').addEventListener('submit',e=>{e.preventDefault();try{const next={schema_version:1,title:$('portal-title').value.trim(),base_url:$('base-url').value.trim(),services:{}};for(const s of services){const url=$(`url-${s.id}`).value.trim();next.services[s.id]={title:$(`title-${s.id}`).value.trim(),order:Number($(`order-${s.id}`).value),icon:$(`icon-${s.id}`).value,enabled:$(`enabled-${s.id}`).checked,favorite:$(`favorite-${s.id}`).checked};if(url)next.services[s.id].url=url;}saveLocal(next);$('settings-dialog').close();notify('Seu espaço foi atualizado.');}catch(error){$('settings-error').textContent=error.message;}});
$('reset-preferences').addEventListener('click',()=>{try{localStorage.removeItem(storageKey);}catch{}local={};update();$('settings-dialog').close();notify('Configuração do servidor restaurada neste navegador.');});
$('search-input').addEventListener('input',()=>{activeResult=0;renderSearch();});
$('search-input').addEventListener('keydown',e=>{if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();const size=$('search-results').children.length;activeResult=Math.max(0,Math.min(size-1,activeResult+(e.key==='ArrowDown'?1:-1)));renderSearch();$('search-results').children[activeResult]?.scrollIntoView({block:'nearest'});}if(e.key==='Enter'){e.preventDefault();$('search-results').querySelector('[data-active=true]')?.click();$('search-dialog').close();}});
$('search-trigger').addEventListener('click',openSearch);document.querySelectorAll('[data-settings]').forEach(b=>b.addEventListener('click',openSettings));document.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',()=>$(b.dataset.close).close()));
for(const d of document.querySelectorAll('dialog'))d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){for(const dialog of document.querySelectorAll('dialog[open]'))dialog.close();}if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();if(!$('search-dialog').open)openSearch();}});
$('favorites-filter').addEventListener('click',()=>{onlyFavorites=!onlyFavorites;update();});
function navigate(){const found=GROUPS.find(g=>g.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'')===location.hash.slice(1));group=found||'Início';if(services.length)update();}
window.addEventListener('hashchange',navigate);
for(const [index,name]of GROUPS.entries()){const a=element('a',`nav-item${name==='Admin'?' admin':''}`);a.href='#'+['inicio','midia','biblioteca','sistema','admin'][index];a.dataset.group=name;a.append(icon(['home','play','book','activity','shield'][index]),element('span','',name));if(name==='Admin')a.append(icon('lock'));$('navigation').append(a);}
icons();
try{const responses=await Promise.all([fetch('/services.json'),fetch('/api/config',{cache:'no-store'})]);if(responses.some(r=>!r.ok))throw new Error('Não foi possível carregar a configuração do portal.');[services,server]=await Promise.all(responses.map(r=>r.json()));validateConfig(server,services);try{const value=localStorage.getItem(storageKey);if(value)local=JSON.parse(value);validateConfig(mergeConfig(server,local),services);}catch{local={};notify('Preferências locais inválidas foram ignoradas.');}navigate();}catch{document.querySelector('.hero').hidden=true;$('service-grid').replaceChildren(element('p','empty','Configuração indisponível. Revise o arquivo privado do portal e recarregue a página.'));document.querySelector('.access-note p').textContent='O portal não conseguiu carregar os atalhos; nenhum estado de serviço foi inferido.';}
