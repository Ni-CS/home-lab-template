# Home Lab Template

[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![NVIDIA GPU](https://img.shields.io/badge/NVIDIA-GPU%20Accelerated-76B900.svg)](https://developer.nvidia.com/cuda-zone)
[![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-red.svg)](https://github.com/)

Um template "plug-and-play" e parametrizado para construir o seu próprio laboratório pessoal focado em Inteligência Artificial, Mídia e Produtividade. Substitua serviços em nuvem pagos pelas suas próprias alternativas locais, rodando no seu hardware de forma segura e privada.

---

## A Stack (O que tem no home-lab?)

Este repositório orquestra os seguintes serviços através de um arquivo `docker-compose.yml` otimizado:

* **🏠 Dashboard & Monitoramento:** [Homepage](https://gethomepage.dev/) (Painel inicial) e [Glances](https://nicolargo.github.io/glances/) (Telemetria do sistema).
* **🤖 Inteligência Artificial:** [Ollama](https://ollama.com/) + [Open WebUI](https://openwebui.com/) (Seu ChatGPT privado), [Fooocus](https://github.com/lllyasviel/Fooocus) (Geração de imagens SDXL) e **Jupyter/Colab Local** (Ambiente de estudos e visão computacional).
* **🍿 Mídia & Áudio:** [Jellyfin](https://jellyfin.org/) (Sua Netflix particular), [Navidrome](https://www.navidrome.org/) + [MusicBrainz Picard](https://picard.musicbrainz.org/) (Seu Spotify privado).
* **📸 Fotos:** [Immich](https://immich.app/) (Backup de fotos estilo Google Fotos, com IA para busca facial e de objetos).
* **📚 Leitura:** [Kavita](https://www.kavitareader.com/) (Servidor de quadrinhos, mangás e e-books).
* **🗂️ Ferramentas:** [FileBrowser](https://filebrowser.org/) (Gerenciador de arquivos web estilo Google Drive).

---

## 📋 Pré-requisitos

1. **Sistema Operacional:** Linux (Ubuntu/Debian recomendado).
2. **Docker Engine & Docker Compose V2** instalados.
3. **GPU NVIDIA (Opcional, mas altamente recomendado):** Para os serviços de IA e transcodificação de vídeo. Requer a instalação do [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
4. **Tailscale (Opcional):** Para acesso remoto seguro (veja a seção *Acesso Remoto* abaixo).

---

## Instalação e Uso (Passo a Passo)

A arquitetura foi desenhada para não poluir o sistema operacional do host. Tudo é parametrizado.

### 1. Clone o repositório
```bash
git clone [https://github.com/SEU_USUARIO/ai-homelab-template.git](https://github.com/SEU_USUARIO/ai-homelab-template.git)
cd ai-homelab-template
```

### 2. Configure as Variáveis de Ambiente
Copie o template do arquivo de configuração e preencha com os seus dados:
```bash
cp .env.example .env
nano .env
```

**Importante**: Altere a variável DATA_PATH para apontar para o disco rígido (HD/SSD) onde você deseja salvar as mídias, modelos de IA e bancos de dados. Troque também as senhas padrão.

### 3. Dê permissão aos scripts de gerenciamento
O repositório inclui scripts utilitários para facilitar a sua vida. Torne-os executáveis:
```bash
chmod +x scripts/*.sh
```

### 4. Inicialize a Estrutura (Setup)
Execute o script de setup. Ele vai ler o seu .env, criar todas as pastas no seu HD de forma organizada e preparar os arquivos de banco de dados locais.
```bash
./scripts/setup.sh
```
### 5. Ligue o Lab!
Use o script de controle interativo para ligar os containers. Ele evita a necessidade de digitar comandos complexos do Docker.
```bash
./scripts/control.sh
```

Escolha a opção 1 para ligar tudo, ou escolha módulos específicos. O painel inicial estará disponível no IP do seu servidor na porta 80 (ex: `http://localhost`).

(Opcional: Para baixar o modelo de geração de imagens do Fooocus, execute `./scripts/download_models.sh`).

## Acesso Remoto Seguro (Tailscale)
Nunca abra as portas do seu Home Lab (como 80, 3000, 8096) diretamente no seu roteador para a internet. Isso expõe seus arquivos e poder de processamento a ataques.

A melhor prática DevOps para acessar seu laboratório de qualquer lugar do mundo (4G, Wi-Fi do trabalho, viagens) é usando o Tailscale.
1. Instale o Tailscale no seu Servidor Home Lab.
2. Instale o app do Tailscale no seu celular ou notebook pessoal.
3. O Tailscale criará uma VPN Mesh (WireGuard) e dará ao seu servidor um IP privado seguro (ex: 100.x.x.x).
4. Basta digitar esse IP 100.x.x.x no navegador do seu celular quando estiver na rua, e você terá acesso ao seu Dashboard, Jellyfin e Open WebUI como se estivesse no sofá de casa!

## Documentação Detalhada
Cada serviço possui suas particularidades, caminhos de pastas e credenciais padrão de primeiro acesso. Preparamos guias rápidos para cada categoria na pasta `docs/`.

Consulte antes de usar:
* IA: [Ollama & WebUI](docs/ai/ollama-webui.md) | [Fooocus](docs/ai/fooocus.md) | [Colab Local](docs/ai/colab-local.md)
* Mídia: [Jellyfin](docs/media/jellyfin.md) | [Navidrome & Picard](docs/media/navidrome-picard.md)
* Fotos: [Immich](docs/photos/immich.md)
* Ferramentas: [FileBrowser](docs/tools/filebrowser.md) | [Kavita](docs/reading/kavita.md)

---
