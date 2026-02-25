# Ambiente de Estudos (Colab Local / Jupyter)

Este serviço roda a imagem oficial do Google Colab no seu servidor. Ele permite que você execute notebooks Jupyter aproveitando o poder da sua GPU local, sem limites de tempo ou quedas de conexão do Google Colab gratuito.

## Como Acessar
Diferente dos outros serviços, o Jupyter exige um **Token de Segurança** a cada reinicialização para garantir que apenas você acesse o código.

1. Inicie o serviço pelo script (`./scripts/control.sh` -> Opção 5).
2. O script capturará o token dos logs do Docker e exibirá o link correto no terminal.
3. O link será algo como: `http://<IP_DO_SERVIDOR>:8899/?token=seu_token_aqui`

## Conectando ao Site do Google Colab (Opcional)
Se você preferir usar a interface do próprio site do Google Colab em vez do Jupyter Lab cru:
1. Abra o site do [Google Colab](https://colab.research.google.com/).
2. No canto superior direito, clique na seta ao lado de "Connect" (Conectar).
3. Escolha **"Connect to a local runtime"** (Conectar a um ambiente de execução local).
4. Cole o link com o token gerado pelo script na porta `8899`.

## Onde os notebooks ficam salvos?
Para não perder seus estudos caso o container seja destruído, salve todos os seus arquivos de código, datasets e projetos dentro da pasta `/content` no Jupyter.

Essa pasta está mapeada diretamente para o seu HD físico em:
`$DATA_PATH/study`
