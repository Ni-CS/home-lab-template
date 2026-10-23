# ADR-003 — Portal próprio, isolado do Homepage

Aceito pelo pedido de 2026-10-22. Portal próprio com catálogo sanitizado,
preferências privadas e sem controle Docker; Homepage preservado como fallback.
O registro npm ficou inacessível no ambiente de execução e não havia cache Next.
Foi implementada uma aplicação de módulos ES/CSS com build Python offline, sem
backend de escrita, banco ou bibliotecas externas. Isso permite entregar e testar
agora a interface completa. A preferência por Next/TypeScript/Tailwind/shadcn não
foi adotada nesta versão. O custo é manter pequenos componentes e ícones locais.

Disponibilidade desconhecida até integração real. Admin é navegação, sem ações,
e depende da autenticação dos serviços de destino. O módulo CPU `portal` é opt-in,
sem dependências, com bind loopback por padrão e configuração montada read-only.
Nenhum acesso LAN/tailnet é alterado sem autorização; runtime Docker e essa rota
continuam não verificados. Rollback mantém Homepage e as rotas atuais.
