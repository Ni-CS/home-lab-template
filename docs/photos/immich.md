# Galeria de Fotos e Backup (Immich)

O Immich é a melhor alternativa self-hosted ao Google Fotos. Ele faz backup automático do seu celular e utiliza Inteligência Artificial para reconhecimento facial e busca por objetos nas imagens.

## Como Acessar
1. Inicie o serviço de galeria (`./scripts/control.sh` -> Opção 8).
2. Acesse pelo navegador: `http://<IP_DO_SERVIDOR>:2283`
3. Crie sua conta de administrador clicando em "Getting Started".

## Backup do Celular
A verdadeira mágica do Immich está no app mobile:
1. Baixe o aplicativo "Immich" na Play Store ou App Store.
2. Na tela de login do app, coloque o endereço do seu servidor (ex: `http://192.168.x.x:2283`).
3. Faça login e ative o **Backup Automático** nas configurações do aplicativo.

## Inteligência Artificial e GPU
O nosso template já inclui o container `immich-machine-learning` configurado para usar a sua placa de vídeo NVIDIA. Isso torna o reconhecimento de rostos e a clip-search (ex: buscar por "cachorro na praia") extremamente rápidos.

## Atenção aos Caminhos e Banco de Dados
A documentação completa das variáveis de ambiente suportadas pode ser encontrada em https://docs.immich.app/install/environment-variables

O Immich salva os dados em dois lugares essenciais:
1. **Suas Fotos (Uploads):** Salvas na pasta apontada pela variável `UPLOAD_LOCATION` (por padrão: `$DATA_PATH/immich/library`).
2. **Banco de Dados:** Salvo em `$DATA_PATH/immich/postgres`. É altamente recomendado que esta pasta esteja em um disco local, pois o compartilhamento de rede não é suportado para o banco de dados.

Caso queira fixar uma versão específica para evitar atualizações com quebra de compatibilidade, você pode alterar a variável `IMMICH_VERSION` no seu arquivo `.env` (ex: "v2.1.0").
