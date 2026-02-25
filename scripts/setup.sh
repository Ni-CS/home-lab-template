#!/bin/bash

# Garante que o script rode a partir da raiz do projeto
cd "$(dirname "$0")/.." || exit 1

echo "========================================"
echo "    SETUP: AI HOME LAB TEMPLATE"
echo "========================================"

# Verifica se o .env existe
if [ ! -f .env ]; then
    echo "Erro: Arquivo .env não encontrado!"
    echo "Passo 1: Copie o arquivo .env.example para .env"
    echo "Passo 2: Preencha a variável DATA_PATH dentro do .env"
    echo "Passo 3: Rode este script novamente."
    exit 1
fi

# Carrega as variáveis do .env ignorando as linhas comentadas
# shellcheck disable=SC2046
export $(grep -v '^#' .env | xargs)

# Verifica se o DATA_PATH foi preenchido com um valor válido
if [ -z "$DATA_PATH" ] || [[ "$DATA_PATH" == *"/caminho/para/seu/"* ]]; then
    echo "Erro: A variável DATA_PATH no .env não foi configurada corretamente."
    echo "Abra o .env e aponte para a pasta real do seu HD (ex: /mnt/dados)."
    exit 1
fi

echo "1/3 Criando estrutura externa de armazenamento em: $DATA_PATH"
# Cria os diretórios no HD do usuário para evitar erro de permissão do Docker
mkdir -p "$DATA_PATH/media/musicas"
mkdir -p "$DATA_PATH/biblioteca"
mkdir -p "$DATA_PATH/fooocus/models"
mkdir -p "$DATA_PATH/fooocus/outputs"
mkdir -p "$DATA_PATH/immich/postgres"
mkdir -p "$DATA_PATH/immich/library"
mkdir -p "$DATA_PATH/study"

echo "2/3 Criando pastas locais de configuração (configs/)..."
mkdir -p ./configs/homepage/images
mkdir -p ./configs/homepage/icons
mkdir -p ./configs/kavita
mkdir -p ./configs/picard
mkdir -p ./configs/filebrowser
mkdir -p ./configs/jellyfin
mkdir -p ./configs/navidrome

echo "3/3 Inicializando banco de dados vazios..."
# Evita o erro do Docker Compose criar o db do FileBrowser como diretório
touch ./configs/filebrowser/filebrowser.db

echo "========================================"
echo "Setup finalizado com sucesso!"
echo "Próximo passo: ./scripts/control.sh"
echo "========================================"
