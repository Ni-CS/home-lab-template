# Leitor de Quadrinhos, Mangás e PDFs (Kavita)

O Kavita é um servidor de leitura ultrarrápido focado em quadrinhos (CBR/CBZ), mangás, PDFs e e-books (EPUB). Ele lembra a interface de serviços de streaming, mas voltado para a leitura, salvando seu progresso e permitindo ler diretamente no navegador do PC, tablet ou celular.

## Como Acessar
1. Inicie a biblioteca (`./scripts/control.sh` -> Opção 9).
2. Acesse: `http://<IP_DO_SERVIDOR>:5000`

## Primeiro Acesso
Logo no primeiro acesso, o Kavita pedirá para você criar a conta do Administrador (Admin). Insira seu e-mail, crie um nome de usuário e uma senha segura.

## Como Adicionar suas Leituras
Para o Kavita reconhecer seus arquivos, primeiro você precisa colocar os seus PDFs, EPUBs ou CBZs na pasta designada no seu HD:
`$DATA_PATH/biblioteca/`

**Dica de Organização:**
O Kavita funciona muito melhor se você separar as mídias por tipo. Crie subpastas pelo FileBrowser ou no seu sistema operacional, por exemplo:
* `$DATA_PATH/biblioteca/Mangas/`
* `$DATA_PATH/biblioteca/Artigos_PDF/`
* `$DATA_PATH/biblioteca/Quadrinhos/`

## Criando as Bibliotecas no Kavita
Depois de colocar os arquivos nas pastas, você precisa dizer ao Kavita para escaneá-las:
1. No painel do Kavita, clique no ícone de engrenagem (Server Settings) no canto superior direito.
2. Vá na aba **Libraries** e clique em **Add Library**.
3. Dê um nome (ex: "Meus Mangás") e escolha o tipo correspondente.
4. Na aba **Folders**, clique em "Browse" (Procurar).
5. Você verá uma pasta chamada `/libraries`. Clique nela! Essa é a ponte do Docker para a sua pasta `$DATA_PATH/biblioteca/` do mundo real.
6. Selecione a subpasta desejada e clique em "Save".

O Kavita fará um scan e baixará os metadados automaticamente. Aproveite a leitura!
