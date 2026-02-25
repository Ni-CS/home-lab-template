# Cérebro & Chat (Ollama + Open WebUI)

Este módulo transforma o seu Home Lab em uma alternativa local e 100% privada ao ChatGPT, rodando os modelos diretamente no seu hardware.

## Como Acessar
1. Certifique-se de ter iniciado a stack de IA (`./scripts/control.sh` -> Opção 3).
2. Acesse: `http://<IP_DO_SERVIDOR>:3000`

## Primeiro Acesso e Configuração
O Open WebUI requer autenticação para proteger o seu histórico de chat.
1. Na tela de login, clique em **"Sign Up"** (Registrar).
2. O **primeiro usuário** criado se tornará automaticamente o Administrador do sistema.
3. *Nota de Segurança:* A segurança das sessões é garantida pela variável `WEBUI_SECRET_KEY` configurada no seu arquivo `.env`.

## Como baixar Modelos de IA (LLMs)
Por padrão, o Ollama vem vazio. Você precisa baixar os modelos que deseja usar:
1. Faça login no Open WebUI com sua conta de Administrador.
2. Clique no ícone do seu perfil (canto inferior esquerdo) e vá em **Settings (Configurações)** -> **Admin Settings**.
3. Acesse a aba **Models**.
4. Na seção "Pull a model from Ollama.com", digite o nome do modelo e clique na nuvem para baixar.

**Modelos Recomendados para começar:**
* `llama3.2` (Excelente para tarefas gerais e programação)
* `deepseek-r1` (Ótimo raciocínio lógico)
* `phi3` (Leve e rápido)

## Onde os dados ficam salvos?
* **Modelos do Ollama:** Salvos no volume Docker interno `ollama_data`.
* **Histórico de Chats:** Salvo no volume Docker interno `open-webui_data`.
