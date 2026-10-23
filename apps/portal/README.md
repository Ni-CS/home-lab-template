# Portal HomeLab

Portal pessoal responsivo, sem dependências npm, fontes remotas, rastreadores ou
telemetria inventada. Sete assets públicos gerados a partir do catálogo sanitizado.
Favoritos, busca com Ctrl/Cmd K, navegação por atividade, preferências por navegador.
Admin contém **somente links**; os destinos exigem sua própria autenticação.

```bash
python3 apps/portal/manage.py build --output-dir /tmp/homelab-portal-build
python3 apps/portal/manage.py serve --directory /tmp/homelab-portal-build --port 3100
```

Abra `http://127.0.0.1:3100`. O destino do build precisa ser novo. Para usar
URLs reais, copie `config.example.json` para `portal.local.json` (ignorado), defina
`base_url` com **protocolo e hostname sem porta**, e passe
`--config apps/portal/portal.local.json`. Nenhuma configuração real é incluída no
build. Também é possível configurar endereços em Personalizar; nesse caso ficam
apenas no armazenamento local do navegador. Não são sincronizados entre aparelhos.
Não coloque senhas, tokens, parâmetros, cookies ou configuração de autenticação
nesse arquivo. Configuração inválida falha fechada, sem vazar detalhes nas respostas.

As portas e paths dos links vêm de `catalog/services.json`; apenas títulos, ícones,
atividade e destaque ficam em `catalog/portal-ui.json`. O arquivo privado pode
sobrescrever `title`, `base_url` e, por ID em `services`, `url`, `title`, `order`,
`icon`, `favorite`, `enabled`. URLs específicas prevalecem sobre a base. O estado
é sempre desconhecido: o portal não consulta apps, Docker, Kuma ou Glances.

```bash
node tests/portal-model.mjs
python3 -m unittest discover -s tests -p 'test_portal.py' -q
```

O smoke test `node tests/portal-browser.mjs` usa Node 22+, Chrome de teste com
CDP em loopback `19229` e preview com configuração sintética/privada em `3100`.
Não use seu perfil de navegador pessoal. Ele altera somente preferências do
navegador de teste e captura desktop/mobile em `/tmp/homelab-portal-captures`.

## Docker e CLI

`python3 scripts/homelab.py plan --select portal` seleciona o novo módulo CPU,
sem dependências próprias. `render`/`wizard` incluem os essenciais **de uma nova
instalação**. A evidência histórica continua com 44 serviços e 11 templates;
o novo módulo fica separado em `catalog/modules.json`. Nunca use esse projeto
novo para substituir o Compose pessoal.

O Dockerfile tem build offline e runtime Python sem dependências adicionais.
A imagem base `python:3.12-slim-bookworm` recebe patches dentro da série: atualização
manual e build revisado; digest não fixado. O módulo publica **somente loopback**
`3100`, filesystem read-only, UID/GID `65532`, sem capabilities, sem socket Docker
ou diretórios pessoais. `/config/portal.json` contém apenas URLs/preferências e
entra como montagem somente leitura. O healthcheck mede só a resposta do portal.
Instalação Docker e comportamento sob essas restrições ainda exigem teste no host.

Para teste independente, após revisar capacidade e aprovar criação do container:

```bash
docker build -f apps/portal/Dockerfile -t homelab-portal:local .
# Use um diretório novo contendo portal.json (0644), com diretório legível (0755).
# Os caminhos abaixo são apenas exemplos genéricos; não usar configs pessoais.
docker run -d --name homelab-portal --read-only --user 65532:65532 \
  --cap-drop ALL --security-opt no-new-privileges \
  --log-driver local --log-opt max-size=10m --log-opt max-file=3 \
  -p 127.0.0.1:3100:8080 \
  --mount type=bind,source=/srv/homelab/portal-config,target=/config,readonly \
  homelab-portal:local
```

O preview é **loopback** e não fica acessível no celular por Tailscale ainda.
A publicação LAN/tailnet requer aprovação separada da rota/bind e verificação no
celular. Um NPM em container não acessa o loopback do host como seu próprio
localhost: definir uma rede Docker compartilhada explicitamente e usar o serviço
como upstream, ou uma rota de host validada, mantendo o bind privado. Não adicionar
Funnel, abrir portas no roteador nem alterar DNS/ACL automaticamente. O portal
não autentica visitantes; limitar acesso à LAN/tailnet confiável. Homepage mantém
sua configuração/URL atual como fallback. Rollback: manter o acesso ao Homepage;
nenhuma rota atual foi substituída.
