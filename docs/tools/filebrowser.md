# Gerenciador de Arquivos Web (FileBrowser)

O FileBrowser é o seu "Google Drive" local. Ele cria uma interface web limpa e rápida para você enviar, apagar, mover e renomear arquivos diretamente no seu servidor, sem precisar usar FTP, SSH ou linha de comando.

## Como Acessar
1. Inicie o serviço (`./scripts/control.sh` -> Opção 10).
2. Acesse pelo navegador: `http://<IP_DO_SERVIDOR>:8085`

## Credenciais Padrão
No seu primeiro acesso, use as credenciais padrão do sistema:
* **Usuário:** `admin`
* **Senha:** `admin`

**MUITO IMPORTANTE:** Assim que fizer o login, vá em **Settings (Configurações) -> Profile Management** e altere a sua senha imediatamente por motivos de segurança!

## Como ele funciona?
O FileBrowser está mapeado diretamente para a raiz do seu armazenamento definido no `.env` (a variável `$DATA_PATH`). 

Isso significa que, através dele, você tem acesso irrestrito a todas as outras pastas do seu Home Lab. Você pode:
* Fazer upload de `.mp3` direto para a pasta do Navidrome.
* Arrastar e soltar vídeos do seu PC direto para a pasta do Jellyfin.
* Organizar seus PDFs na pasta do Kavita.

## Permissões de Arquivos
O script de setup configurou o FileBrowser para rodar com os mesmos IDs de usuário (`PUID` e `PGID`) da sua máquina host. Isso garante que os arquivos que você criar ou enviar pela interface web poderão ser lidos, editados ou apagados normalmente no seu sistema operacional nativo, evitando o erro de "arquivo preso como root".
