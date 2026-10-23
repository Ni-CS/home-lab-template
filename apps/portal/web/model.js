export const GROUPS = ['Início', 'Mídia', 'Biblioteca', 'Sistema', 'Admin'];
export const ICONS = ['aperture','music','play','folder','book','notebook','activity','chart','grid','shield','network'];
export function safeUrl(value, allowEmpty = true) {
  if (allowEmpty && value === '') return '';
  if (typeof value !== 'string' || /[\u0000-\u0020\\]/.test(value)) throw new Error('Use uma URL HTTP ou HTTPS sem espaços.');
  let u; try { u = new URL(value); } catch { throw new Error('Informe um endereço completo, como http://seu-servidor.'); }
  if (!['http:', 'https:'].includes(u.protocol) || !u.hostname || u.username || u.password || u.search || u.hash)
    throw new Error('Não inclua credenciais, tokens ou parâmetros nos endereços.');
  if (['localhost','127.0.0.1','[::1]','0.0.0.0','[::]'].includes(u.hostname)) throw new Error('Use um hostname LAN ou Tailscale acessível por outros dispositivos.');
  return u.href;
}
export function validateConfig(config, services) {
  if (!config || typeof config !== 'object' || Array.isArray(config) || config.schema_version !== 1 ||
      Object.keys(config).some(k => !['schema_version','title','base_url','services'].includes(k))) throw new Error('Configuração inválida.');
  if (typeof config.title !== 'string' || !config.title.trim() || config.title.length > 40) throw new Error('O nome deve ter de 1 a 40 caracteres.');
  safeUrl(config.base_url);
  if (config.base_url) { const u = new URL(config.base_url); if (u.port || u.pathname !== '/') throw new Error('O endereço base deve conter somente protocolo e hostname.'); }
  if (!config.services || Array.isArray(config.services) || typeof config.services !== 'object') throw new Error('Atalhos inválidos.');
  for (const [id, entry] of Object.entries(config.services)) {
    if (!services.some(s => s.id === id) || !entry || typeof entry !== 'object' || Array.isArray(entry) ||
        Object.keys(entry).some(k => !['title','url','order','icon','favorite','enabled'].includes(k))) throw new Error('Preferência de serviço inválida.');
    if (entry.url !== undefined) safeUrl(entry.url);
    if (entry.title !== undefined && (typeof entry.title !== 'string' || !entry.title.trim() || entry.title.length > 60)) throw new Error('Título inválido.');
    if (entry.icon !== undefined && !ICONS.includes(entry.icon)) throw new Error('Ícone inválido.');
    if (entry.order !== undefined && (!Number.isInteger(entry.order) || entry.order < 0 || entry.order > 1000)) throw new Error('Ordem inválida.');
    for (const key of ['favorite','enabled']) if (entry[key] !== undefined && typeof entry[key] !== 'boolean') throw new Error('Preferência inválida.');
  }
  return config;
}
export function mergeConfig(server, local) {
  const services = Object.fromEntries([...new Set([...Object.keys(server.services), ...Object.keys(local?.services || {})])].map(id => [id, {...server.services[id], ...local?.services?.[id]}]));
  return {...server, ...local, services};
}
export function destinations(services, config) {
  return services.map((s, index) => {
    const custom = config.services[s.id] || {};
    let url = '';
    if (config.base_url && s.navigation) { const base = new URL(config.base_url); base.protocol = `${s.navigation.scheme}:`; base.port = String(s.navigation.port); base.pathname = s.navigation.path; url = base.href; }
    if (custom.url !== undefined) url = custom.url;
    return {...s, order:index, ...custom, url};
  }).filter(s => s.enabled !== false).sort((a,b) => a.order - b.order);
}
export function matches(service, query) {
  return `${service.title} ${service.description} ${service.group} ${service.eyebrow}`.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().includes(query.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase());
}
