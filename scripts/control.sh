#!/bin/bash

# Garante que o script rode a partir da raiz do projeto, não importa de onde seja chamado
cd "$(dirname "$0")/.." || exit 1

# Carrega variáveis do .env (se existir) para montar os links de acesso corretamente
if [ -f .env ]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' .env | xargs)
fi
HOST_IP=${SERVER_IP:-localhost}

echo "========================================"
echo "      CONTROLE HOME LAB TEMPLATE     "
echo "========================================"
echo "1.  Ligar TUDO"
echo "2.  Ligar Dashboard & Monitoramento"
echo "3.  Ligar IA (Ollama - Chat)"
echo "4.  Ligar IA (Fooocus - Imagens)"
echo "5.  Ligar IA (Colab Local - Estudos)"
echo "6.  Ligar Mídia (Jellyfin - Vídeo)"
echo "7.  Ligar Mídia (Navidrome - Música)"
echo "8.  Ligar Galeria (Immich - Fotos)"
echo "9.  Ligar Leitura (Kavita)"
echo "10. Ligar Arquivos (FileBrowser)"
echo "0.  Desligar TUDO"
echo "========================================"
read -p "Escolha uma opção: " opcao

case $opcao in
    1) 
        echo "Ligando todos os containers principais..."
        docker compose up -d 
        ;;
    2) 
        echo "Ligando Painel e Monitoramento..."
        docker compose up -d homepage glances 
        echo "Acesse o Dashboard em: http://${HOST_IP}:80"
        ;;
    3) 
        echo "Ligando Cérebro IA (Ollama + Open WebUI)..."
        docker compose up -d ollama open-webui 
        echo "Acesse o Chat em: http://${HOST_IP}:3000"
        ;;
    4) 
        echo "Preparando Pincéis (Fooocus)..."
        docker compose up -d fooocus 
        echo "Acesse o Fooocus em: http://${HOST_IP}:7865"
        ;;
    5)
        echo "Ligando Ambiente de Estudos (Colab Local)..."
        docker compose up -d colab-local
        echo "Aguardando o Token ser gerado (5s)..."
        sleep 5
        echo "----------------------------------------"
        # Extrai o token diretamente do log usando regex
        TOKEN=$(docker logs colab-local 2>&1 | grep -oP '(?<=token=)[a-zA-Z0-9]+' | tail -n 1)
        if [ -n "$TOKEN" ]; then
            echo "Acesse: http://${HOST_IP}:8899/?token=${TOKEN}"
        else
            echo "Acesse: http://${HOST_IP}:8899 (Verifique os logs com 'docker logs colab-local' para o token)"
        fi
        echo "----------------------------------------"
        ;;
    6) 
        echo "Preparando a Pipoca (Jellyfin)..."
        docker compose up -d jellyfin 
        echo "Acesse o Jellyfin em: http://${HOST_IP}:8096"
        ;;
    7)
        echo "Ligando os alto-falantes (Navidrome + Picard)..."
        docker compose up -d navidrome picard
        echo "Acesse o Navidrome em: http://${HOST_IP}:4533"
        echo "Acesse o Picard em: http://${HOST_IP}:5800"
        ;;
    8)
        echo "Ligando Immich (Fotos + ML)..."
        docker compose up -d immich-server immich-machine-learning
        echo "Acesse o Immich em: http://${HOST_IP}:2283"
        ;;
    9)
        echo "Abrindo a Biblioteca (Kavita)..."
        docker compose up -d kavita
        echo "Acesse o Kavita em: http://${HOST_IP}:5000"
        ;;
    10) 
        echo "Abrindo escritório virtual (FileBrowser)..."
        docker compose up -d filebrowser
        echo "Acesse o FileBrowser em: http://${HOST_IP}:8085"
        ;;
    0)
        echo "Hibernando o Lab..."
        docker compose stop
        ;;
    *) 
        echo "Opção inválida!" 
        ;;
esac
