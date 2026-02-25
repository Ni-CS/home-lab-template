FROM ghcr.io/lllyasviel/fooocus:latest

USER root
WORKDIR /content/app

# ==============================================================================
# ATENÇÃO USUÁRIOS DE GPUs RECENTES (Ex: NVIDIA RTX 50-Series)
# A imagem base suporta nativamente a maioria das placas (séries 10 a 40).
# Se você tiver erros de compatibilidade de arquitetura, DESCOMENTE as 
# linhas abaixo para compilar o PyTorch com suporte ao CUDA 12.8+.
# ==============================================================================

# RUN pip uninstall -y torch torchvision torchaudio xformers
# RUN pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
# ENV TORCH_CUDA_ARCH_LIST="9.0 10.0"

# Mantém as permissões dinâmicas para evitar erros ao mapear volumes externos
RUN chmod -R 777 /content/app
