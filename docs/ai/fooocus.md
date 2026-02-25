# Geração de Imagens (Fooocus)

O Fooocus é uma interface de geração de imagens baseada no Stable Diffusion (SDXL) com foco em simplicidade, entregando resultados no nível do Midjourney de forma totalmente offline.

## Como Acessar
1. Inicie o container (`./scripts/control.sh` -> Opção 4).
2. Acesse: `http://<IP_DO_SERVIDOR>:7865`

## Instalação dos Modelos (Checkpoints)
O Fooocus precisa de arquivos de pesos pesados (Checkpoints) para funcionar. Para facilitar sua vida, criamos um script automatizado que baixa o modelo padrão de alta qualidade (Juggernaut XL - ~6.6GB).

**Como baixar:**
Execute no terminal:
```bash
./scripts/download_models.sh
```
Os modelos serão salvos automaticamente em: `$DATA_PATH/fooocus/models/checkpoints`.

## Aviso sobre Placas de Vídeo (GPUs)
A imagem base do Fooocus atende nativamente à grande maioria das placas NVIDIA (Séries 10, 20, 30 e 40). O container está configurado para acessar sua GPU automaticamente através das marcações de `deploy` no Docker Compose.

Usuários de Séries Recentes (ex: RTX 50-Series):
Se você possui uma arquitetura super recente e o Fooocus apresentar erros de compilação ou compatibilidade de CUDA, você precisará forçar o uso da versão nightly do PyTorch.

1. Abra o arquivo builds/fooocus/Dockerfile.
2. Descomente as linhas indicadas no código (que desinstalam o Torch padrão e instalam a versão CUDA 12.8+).
3. Reconstrua a imagem rodando: docker compose build fooocus e depois inicie o serviço novamente.

## Onde as imagens geradas ficam salvas?
Todas as suas criações são organizadas por data na pasta:
`$DATA_PATH/fooocus/outputs`
