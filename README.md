# Brick Control — Sistema de Controle de Kits Educacionais

Sistema web para controle e conferência de kits LEGO em escolas de robótica educacional.

## Funcionalidades

- **3 níveis de acesso:** Admin, Pedagogo e Auxiliar
- Catálogo de peças com imagens
- Modelos de kit com composição configurável
- Conferência de kits por peça com histórico
- Gráfico de evolução de saúde por kit
- Geração de etiquetas QR Code para impressão
- Exportação de relatórios em PDF
- CSRF protection em todos os formulários
- Senhas criptografadas com bcrypt
- Logs de auditoria (login, conferências)


## Estrutura de Roles

| Role      | Acesso                                              |
|-----------|-----------------------------------------------------|
| admin     | Tudo: cadastros, usuários, relatórios, conferências |
| pedagogo  | Visualização e relatórios das escolas atribuídas    |
| auxiliar  | Conferência e relatório somente da sua escola       |
