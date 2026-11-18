# Plano de Implementação: RBAC por Perfil na Base de Conhecimento

**Data:** 2026-11-18  
**Branch sugerida:** `feature/kb-rbac-artigos`  
**Escopo:** Controle de acesso (RBAC) por perfil de usuário nos artigos da Base de Conhecimento (`KbArtigo`), permitindo que administradores definam quais perfis podem visualizar artigos novos e existentes.

---

## 1. Diagnóstico do Estado Atual

- **Perfis existentes em `models.py` (`Usuario.perfil`):**
  - `supremo` (e `admin@king.com` via `is_supremo`)
  - `admin` (`is_admin` inclui `supremo`)
  - `operador` (`is_operador`)
  - `tecnicoImpressora` (`is_tecnico_impressora`)
  - `usuario` (padrão)
- **Modelo `KbArtigo` (`models.py`):** Não possui campo de restrição por perfil; apenas `status` (`publicado`, `rascunho`, `arquivado`).
- **Pontos de exposição identificados:**
  - `ConhecimentoService.listar_artigos` (`services/conhecimento_service.py`)
  - `routes/base_conhecimento.py`:
    - `index()` (listagem principal e `artigos_populares`)
    - `ver_artigo(slug)` (leitura, incremento de visualizações e `artigos_relacionados`)
    - `feedback_artigo(artigo_id)` (envio de avaliação)
- **Persistência SQLite:** `app.py` usa `db.create_all()`, que não adiciona colunas em tabelas já existentes no `chamados.db`. Será necessária migração idempotente via `PRAGMA table_info(kb_artigos)` + `ALTER TABLE`.

---

## 2. Arquitetura da Solução

- **Coluna em `KbArtigo`:** `perfis_permitidos = db.Column(db.String(255), nullable=True)`
  - `None` ou vazio (`""`): artigo público para todos os usuários autenticados (retrocompatível com todos os artigos atuais).
  - Lista separada por vírgula (ex.: `"operador,tecnicoImpressora"`): restrito aos perfis listados + `admin`/`supremo` (que sempre têm acesso total).
- **Métodos de domínio em `KbArtigo`:**
  - `@property def lista_perfis_permitidos(self) -> list[str]`
  - `@property def is_restrito(self) -> bool`
  - `def usuario_pode_ver(self, usuario) -> bool`
- **Constante de perfis válidos:** `PERFIS_KB_OPCOES` centralizada para uso consistente entre rotas, serviços e templates.

---

## 3. Decomposição em Etapas / Issues

### Fase 1 — `feat(kb): modelagem e migração idempotente de RBAC em KbArtigo`
- **Objetivo:** Adicionar suporte a `perfis_permitidos` no modelo `KbArtigo` e garantir migração segura do `chamados.db` existente.
- **Arquivos:** `models.py`, `app.py` (ou helper de migração idempotente executado no startup).
- **Critérios de aceitação:**
  - Coluna `perfis_permitidos` criada no banco existente sem perda de dados.
  - `artigo.usuario_pode_ver(usuario)` retorna `True` para `admin`/`supremo`, `True` para artigos sem restrição publicados, e valida `usuario.perfil` quando restrito.

### Fase 2 — `feat(kb): filtragem RBAC na camada de serviço (ConhecimentoService)`
- **Objetivo:** Garantir que listagens, buscas e consultas de artigos respeitem `usuario_pode_ver(usuario)` e não incrementem views antes da validação.
- **Arquivos:** `services/conhecimento_service.py`.
- **Critérios de aceitação:**
  - `listar_artigos` aceita `usuario` e filtra artigos não autorizados.
  - `obter_artigo_por_slug` não incrementa `visualizacoes` se o acesso for negado.

### Fase 3 — `feat(kb): enforcement RBAC nas rotas e salvamento de perfis no editor`
- **Objetivo:** Proteger todas as rotas de leitura/feedback (`403` para não autorizados) e permitir selecionar perfis permitidos ao criar/editar artigos.
- **Arquivos:** `routes/base_conhecimento.py`.
- **Critérios de aceitação:**
  - `index()` filtra `artigos` e `artigos_populares` pelo `current_user`.
  - `ver_artigo(slug)` retorna `403` se `not artigo.usuario_pode_ver(current_user)` e filtra `artigos_relacionados`.
  - `feedback_artigo()` retorna `403` se `not artigo.usuario_pode_ver(current_user)`.
  - `novo_artigo()` e `editar_artigo()` salvam `request.form.getlist('perfis_permitidos')`.
  - `admin_dashboard()` lista todos os artigos (ou com paginação/busca) para que o admin localize facilmente qualquer artigo existente para editar.

### Fase 4 — `feat(kb): seleção de perfis no editor e badge de visibilidade no painel/hub`
- **Objetivo:** Dar ao administrador interface clara para configurar perfis permitidos em artigos novos e existentes e visualizar o status de restrição.
- **Arquivos:** `templates/conhecimento/editor_artigo.html`, `templates/conhecimento/admin_dashboard.html`, `templates/conhecimento/index.html`, `templates/conhecimento/artigo.html`.
- **Critérios de aceitação:**
  - Checkboxes de perfis no `editor_artigo.html` com opção clara de "Público (todos)" quando nenhum perfil específico está marcado.
  - Coluna/badge de visibilidade (`Todos` vs `Restrito`) no `admin_dashboard.html`.
  - Badge discreto de "Acesso Restrito" no `index.html` e `artigo.html` para usuários autorizados.

### Fase 5 — `test(kb): validação de RBAC, graphify update e atualização do AGENTS.md`
- **Objetivo:** Validar isolamento de acesso entre perfis, atualizar o grafo Graphify e documentar a mudança no `AGENTS.md`.
- **Arquivos:** Script de teste em `00-anything/04 - rbac base de conhecimento 2026-11-18/`, `AGENTS.md`, `graphify-out/`.
- **Critérios de aceitação:**
  - Usuário comum recebe `403` ao tentar acessar URL direta de artigo restrito e não o vê na busca, populares ou relacionados.
  - `admin` e perfis selecionados acessam normalmente.
  - `python scripts/atualizar_graphify.py` executado e `AGENTS.md` atualizado.
