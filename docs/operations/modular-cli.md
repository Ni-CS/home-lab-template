# CLI modular — uso

Implementação inicial: catálogo com 44 declarações, 11 módulos com templates,
resolução de dependências, CPU/GPU, wizard e instalação restrita a projeto novo.
Os 33 restantes ficam como `inventory-only`; renderização recusa esses módulos.
Catálogo não prova execução. A instalação pessoal e suas rotas não são migradas.

```bash
python3 scripts/homelab.py validate --check-local
python3 scripts/homelab.py list
python3 scripts/homelab.py plan --select open-webui --hardware cpu
python3 scripts/homelab.py render --select jellyfin --hardware gpu --site templates/modular/site.example.json
```

Default da nova instalação: AdGuard, NPM, Homepage e Uptime Kuma. Opcionais têm
profile e restart `no`. qBittorrent/Prowlarr não dependem da automação de TV;
integrações do Lidarr são exibidas, sem forçar instalação por categoria.
O default do Compose pessoal permanece distinto; não confundir as duas seleções.

## Instalador interativo

Crie configuração local a partir de `templates/modular/site.example.json`, com
data/state separados, bind privado, URLs e mounts esperados. Ela aceita somente
essas configurações e storage adicional; não recebe senhas. Não faz source de .env.
Padrão público é loopback; acesso LAN/tailnet precisa de configuração local explícita.

```bash
python3 scripts/homelab.py wizard --site /caminho/privado/site.local.json --output-dir /tmp/homelab-prepared
python3 scripts/homelab.py doctor --site /caminho/privado/site.local.json --select open-webui --hardware cpu
python3 scripts/homelab.py install --prepared-dir /tmp/homelab-prepared
```

Wizard seleciona módulos/hardware, mostra dependências e gera Compose, seleção,
site local e Homepage em diretório privado novo. Não baixa imagens nem inicia
containers. Doctor verifica paths/mounts, bytes/inodes, portas e GPU quando pedida.
Portas livres no namespace consultado não provam acesso LAN/tailnet.

`install` sem flags de execução só verifica. Para uma instalação **nova**, o
operador pode escolher `--execute --budget-gib N` após revisar custo/extração e
backup. A flag explícita de execução dispensa confirmações adicionais e recusa projeto já existente,
persistência RW preenchida, symlinks, portas ocupadas, configuração adulterada,
mounts/capacidade desconhecidos e falta de orçamento. Não atualiza a instalação
existente. Usa o mesmo guard, com reserva ≥20 GiB + orçamento, ≥10% e ≥5% inodes,
sem reduzir pisos mais estritos do ambiente. Containerd exige storage adicional.

Os diretórios data/state devem existir e ser validados; somente subdiretórios
novos/vazios declarados são criados após verificar storage. Arquivos gerados
da Homepage não substituem configuração existente. Falha pode deixar preparação
nova para revisão; não há limpeza automática. WebUI exige `WEBUI_SECRET_KEY`
fornecido explicitamente ao processo, sem leitura do .env pessoal pelo instalador.

O comando final delega `up` ao guard, fixa o nome do projeto novo e usa
`--no-recreate`, sem órfãos/prune. Isso não substitui testes funcionais/backup.
**Nesta entrega nenhum install --execute foi executado no host; somente mocks.**

## Consolidar Git sem copiar dados pessoais

```bash
python3 scripts/homelab.py baseline check
python3 scripts/homelab.py baseline export --destination /tmp/homelab-public-review
```

O primeiro consulta refs locais (sem fetch), contagens e riscos de arquivos
rastreados. Nesta árvore HEAD/origin-main locais têm 15 serviços e o Compose 44;
há nove configurações rastreadas que exigem revisão. Ignore não remove rastreados.
Export copia somente os arquivos da allowlist `catalog/public-files.json`, após conferir hashes aprovados;
gera manifesto público e recusa overwrite/symlinks. Não copia Compose pessoal,
configs, .env, bancos, uploads ou scripts legados. Não faz git add/commit/push.
O bundle é baseline revisável parcial, não substituto completo dos 44 serviços.
`.git` da árvore original continua restrito; patches são o meio de entrega.

## Homepage, retenção e administração

`homepage --select ... --site ...` exporta services em JSON compatível com YAML,
com URLs locais explícitas e estado desconhecido. NPM aponta à porta administrativa,
AdGuard à porta de setup; overrides de URL suportam proxy/DNS da tailnet. Não há
socket ou controle de containers nos templates. CSS responsivo/foco visível e
busca mobile estão em `templates/homepage/`; o CSS foi aplicado ao arquivo local
antes vazio. Links e settings pessoais existentes foram preservados.

No Compose pessoal, Immich server recebeu logging local 10m/3/compressão e
OliveTin profile admin/restart no. **Containers existentes não foram recriados**:
retenção e política de reinício precisam de aplicação aprovada. OliveTin ainda
pode ter socket RW no runtime antigo; opt-in no YAML não corrige autenticação.
Homepage/Glances antigos também não receberam mudanças de socket nesta entrega.
Fontes: [Docker logging](https://docs.docker.com/engine/logging/configure/),
[Homepage](https://gethomepage.dev/installation/docker/) e
[busca mobile](https://gethomepage.dev/configs/settings/#quick-launch).

## LaTeX privado

```bash
python3 scripts/homelab.py plan --select latex-overleaf --hardware cpu
python3 scripts/homelab.py latex-scaffold --site /caminho/privado/site.local.json --destination /tmp/latex-config --version VERSAO_CE_REVISADA
```

O scaffold exige versão CE 6.x.y explícita; gera três arquivos privados para o
Toolkit, com segredo novo não impresso, Mongo 8/Redis 7.4 próprios, porta 3007
loopback e sibling compiles desativados. Nunca monta socket no compilador.
Não baixa Toolkit/imagens, inicia banco ou altera Tailscale. Integração no checkout
Toolkit, imagem TeX completa, conta inicial, compilação pdf/Xe/LuaLaTeX, BibTeX/Biber,
ZIP, restore e rota privada ainda exigem implantação/teste no host. CE só para
usuários confiáveis; não oferece Sandbox Compiles. Configuração não é editor operante.
Base oficial: [Toolkit config](https://github.com/overleaf/toolkit/blob/master/lib/config-seed/overleaf.rc).
Não ativar Funnel ou acesso público.

## Reset concluído

O mantenedor confirmou os resets manuais, inclusive containers financeiros.
Não repetir. As ferramentas de manifesto anteriores não têm executor destrutivo;
outro reset depende de nova solicitação e revisão por grupo. Música/pessoais e
demais bancos permanecem protegidos. Não há comandos de exclusão nesta entrega.

## Verificação e rollback

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -q
PYTHONDONTWRITEBYTECODE=1 python3 tests/validate_compose_synthetic.py
```

Testes de instalação usam mocks; Compose real valida apenas sintaxe com ambiente
sintético, sem .env/daemon. CPU/GPU foram renderizados, não executados. Runtime,
saúde, compilação e LAN/tailnet permanecem não verificados. Reverter somente hunks
novos/artefatos desta evolução; não resetar a árvore suja nem apagar dados. Mudanças
de runtime futuras têm rollback próprio e autorização antes de interrupções.

## Portal opcional

`plan --select portal`, `render --select portal --site ...` e o wizard incluem o
novo módulo CPU isolado. Os 44 serviços de origem e 11 templates anteriores seguem
intactos como inventário; a extensão tem seu próprio descritor. O instalador cria
apenas configuração de URLs/preferências para ele. Fonte e operação independente:
[portal](../../apps/portal/README.md). Nenhuma rota LAN/tailnet ou Homepage é
substituída. Start do Compose legado com `--profile '*'` inclui módulos removidos:
use seleções explícitas; profiles de reinstalação são opt-in.
