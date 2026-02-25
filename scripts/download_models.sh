#!/bin/bash

# Garante que o script rode a partir da raiz do projeto
cd "$(dirname "$0")/.." || exit 1

echo "========================================"
echo "DOWNLOAD DE MODELOS PARA O FOOOCUS  "
echo "========================================"

# Verifica se o .env existe e carrega as variáveis
if [ ! -f .env ]; then
    echo "Erro: Arquivo .env não encontrado!"
    echo "Rode o setup.sh e configure o repositório primeiro."
    exit 1
fi

# shellcheck disable=SC2046
export $(grep -v '^#' .env | xargs)

if [ -z "$DATA_PATH" ]; then
    echo "Erro: DATA_PATH não configurado no .env!"
    exit 1
fi

# Define a pasta de destino correta baseada no DATA_PATH
CHECKPOINTS_DIR="$DATA_PATH/fooocus/models/checkpoints"
mkdir -p "$CHECKPOINTS_DIR"

echo "Destino: $CHECKPOINTS_DIR"
echo "----------------------------------------"

# Configurações do Modelo Padrão (Juggernaut XL v8)
MODEL_URL="https://huggingface.co/lllyasviel/fav_models/resolve/main/fav/juggernautXL_v8Rundiffusion.safetensors"
MODEL_FILE="$CHECKPOINTS_DIR/juggernautXL_v8Rundiffusion.safetensors"

# Verifica se o modelo já existe para não baixar de novo
if [ -f "$MODEL_FILE" ]; then
    echo "O modelo Juggernaut XL já está instalado!"
    echo "Tamanho atual: $(du -h "$MODEL_FILE" | cut -f1)"
else
    echo "Baixando Juggernaut XL (aprox. 6.6GB)..."
    echo "Isso pode demorar dependendo da sua conexão."
    
    # Usa wget com barra de progresso. Se falhar ou for interrompido, ele pode continuar depois com -c
    wget -c -O "$MODEL_FILE" "$MODEL_URL" --progress=bar:force:noscroll
    
    if [ $? -eq 0 ]; then
        echo "Download concluído com sucesso!"
    else
        echo "Erro durante o download. Tente rodar o script novamente."
        # Remove o arquivo corrompido/incompleto em caso de erro grave (opcional, mas o wget -c costuma lidar bem com isso)
    fi
fi

echo "========================================"
echo "Pronto! Agora você pode ligar o Fooocus."
echo "========================================"
