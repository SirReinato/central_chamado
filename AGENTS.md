# AGENTS.md — Hub Central - SirReinato Brasfort (Central de Chamados & Infraestrutura TI)

> **🤖 LEIA ISTO PRIMEIRO.** Este arquivo é a fonte da verdade e o ponto de entrada obrigatório para qualquer modelo de IA ou agente autônomo (Cursor, Claude, Gemini, Copilot, Codex, ChatGPT etc.) que for analisar, criar, refatorar ou modificar código neste projeto.
> Ele documenta a arquitetura, regras de negócio, convenções de código, stack técnica, modelos de dados, segurança, background jobs, estrutura de pastas e fluxos operacionais. Leia-o **integralmente** antes de inspecionar ou alterar qualquer arquivo.

---

## ⚠️ REGRAS OBRIGATÓRIAS (ARQUIVO, GIT, GESTÃO & ESTRUTURAÇÃO)

### 1. Toda alteração estrutural DEVE atualizar este `AGENTS.md` no mesmo commit/tarefa

Considera-se "alteração estrutural" qualquer uma das seguintes ações (lista não exaustiva):

* Criar, renomear, mover ou remover arquivos e pastas em `routes/`, `services/`, `models.py`, `templates/`, `static/`, `utils/`, `scripts/` ou na raiz.
* Criar, modificar ou remover **blueprints, rotas, views, templates Jinja2, services, decorators ou utilitários**.
* Adicionar, atualizar ou remover **dependências** no `requirements.txt`.
* Adicionar ou alterar **variáveis de ambiente** (e espelhar no `.env.example`).
* Implementar ou alterar **regras de negócio**, modelos de dados SQLAlchemy (`models.py`), schemas, migrações de banco ou integrações externas (GLPI, SNMP, SMTP).
* Adotar novas convenções de arquitetura, padrões de logging, regras de segurança (RBAC, CSRF) ou fluxos de inicialização (`iniciar_servidor.bat`, `app.py`).

**Como atualizar este arquivo após uma alteração estrutural:**
1. Atualize a seção correspondente neste documento (árvore de pastas, tabela de rotas, stack, variáveis de ambiente, modelos de dados, etc.).
2. Registre uma nova entrada na tabela de [Histórico de alterações deste arquivo](#-histórico-de-alterações-deste-arquivo) contendo data (YYYY-MM-DD) e resumo conciso do que mudou.
3. Se a alteração afetar diretamente o operador humano, atualize também a documentação em `docs/` ou o `README.md`.

> ⛔ **Atenção:** Se uma IA finalizar uma tarefa estrutural sem atualizar este arquivo e seu histórico, **a tarefa é considerada incompleta e inválida**.

---

### 2. Fluxo obrigatório de Git: Nova Feature/Fix Branch + Push ao GitHub

Para garantir rastreabilidade, isolamento de escopo e facilidade em auditorias:

* **NUNCA desenvolva ou commite diretamente na branch `main` (ou `master`) no dia a dia**.
* Toda nova implementação, melhoria, refatoração ou correção DEVE ser desenvolvida em uma branch dedicada:
  ```bash
  git checkout -b feature/nome-da-funcionalidade   # Para novas funcionalidades
  git checkout -b fix/nome-da-correcao            # Para correção de bugs
  git checkout -b refactor/nome-do-ajuste         # Para refatorações estruturais
  ```
* **Commits atômicos, granulares e semânticos (Conventional Commits)**:
  * Nunca crie commits genéricos ou vagos (como `"wip"`, `"update"`, `"ajustes"`, `"fix"`).
  * Use o padrão semântico: `feat:`, `fix:`, `refactor:`, `style:`, `docs:`, `chore:`, `test:`, `sec:`.
  * Descreva com clareza o escopo da alteração no título e, sempre que aplicável, inclua no corpo o *o quê* e o *porquê* da mudança.
* **Push obrigatório ao repositório remoto ao concluir**:
  ```bash
  git push -u origin <nome-da-branch>
  ```
  Isso viabiliza a criação imediata de Pull Requests e acompanhamento de versão.

---

### 3. Gestão e Decomposição de Demandas em Issues (Linear / MCP & Modo Copiável)

Sempre que uma nova atualização, funcionalidade ou refatoração for solicitada, o agente DEVE organizar o plano de execução em etapas antes ou durante o desenvolvimento:

1. **Decomposição em Etapas Lógicas e Funcionais**:
   * Divida a solicitação em issues granulares, sequenciais e independentes (ex: *Fase 1: Modelagem e Migração de Dados*, *Fase 2: Camada de Serviço e Validação*, *Fase 3: Rotas e Controle de Acesso RBAC*, *Fase 4: Interface Jinja2 e Feedback Visual*, *Fase 5: Testes e Auditoria*).
   * Cada issue deve ser autossuficiente e conter:
     - **Título claro e semântico** (ex: `feat(glpi): implementar retry com backoff exponencial no GlpiClient`).
     - **Objetivo funcional**: o que essa etapa entrega e por que é necessária.
     - **Passo a passo técnico**: arquivos exatos a criar/alterar e bibliotecas envolvidas.
     - **Critérios de aceitação (DoD)**: como validar que a etapa foi concluída com sucesso.

2. **Criação de Issues com Linear MCP Ativo**:
   * Se o ambiente possuir a integração do **Linear via MCP** habilitada, o agente deve **criar e registrar automaticamente essas issues** no projeto/time correspondente do Linear.

3. **Formato Copiável para Agentes Sem Linear MCP**:
   * Em todas as respostas ou documentações de planejamento, forneça também um bloco claro com o conteúdo exato da **atividade do momento** e das etapas seguintes.
   * Esse bloco deve ser estruturado de forma que o desenvolvedor possa simplesmente **copiar e colar o texto em outro agente ou modelo de IA sem MCP**, e esse agente entenda perfeitamente o contexto, restrições e código esperado.

4. **Replanejamento e Adaptação Dinâmica de Planos Futuros**:
   * Se durante o desenvolvimento surgirem novos requisitos, bloqueios técnicos ou o usuário alterar decisões arquiteturais, o agente DEVE **atualizar imediatamente as issues e etapas futuras**.
   * Nunca prossiga com um plano defasado; o backlog e as próximas etapas devem sempre refletir a realidade mais recente.

---

### 4. Proibição de Arquivos Markdown, Relatórios EGM e Testes na Raiz (`00-anything/`)

* **PROIBIDO** gerar, salvar ou descarregar arquivos de rascunho, drafts, specs temporárias, testes avulsos, relatórios de auditoria/crítica/síntese de agentes EGM (`critic_report.md`, `goldfish_review_report.md`, `implementation_readiness_report.md` etc.) na raiz do repositório.
* A raiz do repositório deve conter **exclusivamente** os arquivos de governança e configuração estruturais (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `README.md`, `app.py`, `models.py`, `requirements.txt`, `iniciar_servidor.bat`, dotfiles essenciais).
* **Diretório Obrigatório (`00-anything/`)**: Todos os arquivos de ideação, design, reviews de EGM, relatórios de subagentes, artefatos de testes ou documentações exploratórias DEVEM ser alocados dentro do diretório `00-anything/` na raiz do projeto.
* **Padrão Obrigatório de Subpastas por Implementação**:
  Sempre que iniciar uma sessão de EGM, brainstorm, refatoração estrutural, suíte de testes ou planejamento de uma nova feature, o agente DEVE criar uma nova subpasta dentro de `00-anything/` seguindo rigorosamente o formato:
  ```text
  00-anything/{sequencial_2_digitos} - {nome-da-implementacao} {data-yyyy-mm-dd}/
  ```
  * Exemplo 1: `00-anything/01 - integracao snmp kyocera 2026-11-10/`
  * Exemplo 2: `00-anything/02 - sincronizacao glpi v2 2026-11-12/`
* **Numeração Sequencial Contínua**: Verifique as subpastas já existentes em `00-anything/` e incremente o numeral sequencial de 2 dígitos (`01`, `02`, `03`...) em ordem cronológica crescente.

---

### 5. Regra de Conformidade com Arquitetura Real (Anti-Alucinação / Zero Pré-Concepção)

* **PROIBIDO ALUCINAR FRAMEWORKS OU ESTRUTURAS DIVERGENTES**: Este projeto **NÃO** é uma Single Page Application em React/Vite/Vue/Angular. É uma aplicação corporativa robusta baseada em **Python + Flask + Jinja2 + Waitress + SQLite (WAL)**. O agente NUNCA deve sugerir ou criar componentes React, styled-components, npm scripts ou TypeScript sem instrução explícita do usuário.
* **Respeito aos Padrões Existentes**:
  - Toda nova rota deve pertencer a um `Blueprint` dentro de `routes/`.
  - Toda lógica de negócio, chamadas externas ou manipulações complexas de dados devem residir em `services/`.
  - Todo acesso a banco deve utilizar os modelos declarados em `models.py` através da instância `db = SQLAlchemy()`.
  - Toda tela deve herdar de `templates/base.html` mantendo a identidade visual, navegação, ícones e cabeçalhos de segurança.

---

### 6. Dependência Obrigatória: `graphify` (Sincronização Contínua com `AGENTS.md`)

* **Presença Obrigatória**: O projeto utiliza `graphify` para mapear grafos de dependências, comunidades de código, rotas e nós centrais ("god nodes").
* **Regras Específicas (`.agents/rules/graphify.md`)**:
  - Para dúvidas sobre arquitetura e relacionamentos entre arquivos, quando `graphify-out/graph.json` existir, execute primeiro `python -m graphify query "<pergunta>"` (CLI) ou consulte `graphify-out/wiki/index.md`.
  - Consulte `graphify-out/GRAPH_REPORT.md` para revisões arquiteturais amplas.
* **Atualização Pós-Modificação**: Após modificar código neste projeto, execute `graphify update .` (ou `python scripts/atualizar_graphify.py`) para manter o grafo sincronizado sem custo de API (AST-only).
* **Job Automático no APScheduler**: A aplicação conta com uma rotina agendada periódica a cada 6 horas (`tarefa_atualizar_graphify`) no `app.py`.

---

## 1. Visão Geral

O **Hub Central - SirReinato Brasfort** é uma plataforma web corporativa full-stack de missão crítica desenvolvida em Python/Flask para centralizar e automatizar as operações de Suporte e Infraestrutura de TI da Brasfort.

O sistema integra em um único painel de alta performance:
1. **Central de Chamados Interna**: Gestão de tickets de suporte local com ciclo de vida completo (Aberto, Em Atendimento, Pendente, Fechado), categorização e atribuição técnica.
2. **Sincronização Bidirecional com GLPI**: Integração com a API REST v2.3 do GLPI Corporativo sob política rigorosa de **Carga Zero** (consultas em lote limitado, cache de token OAuth2 em memória e Circuit Breaker para evitar sobrecarga no servidor central).
3. **Monitoramento Automatizado de Impressoras via SNMP**: Descoberta, diagnóstico e leitura em tempo real de hardware e níveis de suprimentos (toner preto, ciano, magenta, amarelo, cilindro, papel, erros de hardware) de impressoras físicas em rede (Lexmark, HP, Kyocera, Brother, Samsung).
4. **Controle de Estoque de Suprimentos & Histórico**: Rastreabilidade completa de entrada, saída e consumo de toners e insumos com vínculo a impressoras ou setores solicitantes.
5. **Gestão de Itens e Estoque entre Salas de TI**: Controle patrimonial e movimentação atômica de cabos, periféricos, peças e hardware entre a **Sala Principal** e a **Sala TI - 3º Andar**.
6. **Base de Conhecimento (KB / Wiki Técnica)**: Repositório interno de artigos e tutoriais em Markdown, categorias, tags, solicitações de criação de conteúdo por usuários e sistema de feedback/avaliação de utilidade.
7. **Diretório de Ramais Telefônicos**: Consulta rápida e busca instantânea de ramais, colaboradores, departamentos e andares da empresa.
8. **Gerador de Assinaturas de E-mail**: Padronização institucional de assinaturas corporativas HTML para Outlook/Exchange com preview dinâmico e exportação.
9. **Notificações Críticas de E-mail**: Módulo SMTP integrado para despacho automatizado de e-mails institucionais (ex: formulários de Cancelamento de NF do GLPI - ID 36) via Office 365 / Exchange.

* **Status Atual**: Em produção local e disponível para toda a rede local (LAN) corporativa na porta 5000, servido via Waitress WSGI com concorrência segura multi-thread (8 workers) e banco SQLite operando em modo WAL (*Write-Ahead Logging*).

---

## 2. Stack Técnica

| Camada | Tecnologia | Detalhes & Configurações de Produção |
| :--- | :--- | :--- |
| **Linguagem & Runtime** | **Python 3.10+ / 3.11+** | Tipagem dinâmica com type hints onde aplicável, ambiente virtual `venv/` |
| **Framework Web** | **Flask 3.1.x** | Arquitetura modular desacoplada via Blueprints (`routes/`) |
| **Servidor WSGI (Produção)** | **Waitress 3.0.x** | Multi-thread de alta performance (pool de 8 threads), servindo em `0.0.0.0:5000` |
| **Templates & Renderização** | **Jinja2 3.1.x** | Server-Side Rendering (SSR) seguro com herança de `base.html` |
| **Banco de Dados** | **SQLite 3 (Unificado: `chamados.db`)** | Modo WAL (`PRAGMA journal_mode=WAL`), `PRAGMA synchronous=NORMAL`, `busy_timeout=30000`, `timeout=30`, `check_same_thread=False` |
| **ORM & Mapeamento** | **Flask-SQLAlchemy 3.1.x / SQLAlchemy 2.0** | Modelos declarativos com relacionamentos, lazy loading otimizado e constraints |
| **Autenticação & Sessões** | **Flask-Login 0.6.x + Werkzeug** | Gerenciamento de sessão, hashes seguros, `UserMixin`, verificação contínua de status ativo |
| **Controle de Acesso (RBAC)** | **Decorators Customizados** | Perfis: `supremo`, `admin`, `operador`, `tecnicoImpressora`, `usuario` (`utils/decorator.py`) |
| **Proteção Web & Segurança** | **Flask-WTF 1.3.x (CSRFProtect)** | Proteção CSRF global contra ataques Cross-Site Request Forgery |
| **Agendador de Tarefas** | **APScheduler 3.11.x (`BackgroundScheduler`)** | Jobs periódicos: SNMP (1h), GLPI Sync (15min), Graphify Update (6h) |
| **Monitoramento de Hardware** | **PySNMP 7.1.x** | Coleta assíncrona/síncrona de OIDs RFC 3805, contadores de páginas e alertas |
| **Integração GLPI** | **Requests 2.34.x / REST API GLPI v2.3** | Cliente com OAuth2, Circuit Breaker, lote configurável e mascaramento de logs |
| **Serviço de E-mail** | **smtplib / email nativos** | Suporte a TLS/SSL, Microsoft 365 / Exchange com cabeçalhos RFC 5322 ("Send As") |
| **Geração de Documentos** | **ReportLab 5.0.x** | Exportação de relatórios em PDF com paginação avançada (`NumberedCanvas`) |
| **Frontend & Estilo** | **HTML5 + CSS3 + Bootstrap Icons** | CSS puro em `static/css/`, PWA via `manifest.json` e Service Worker (`sw.js`) |
| **Mapeamento de Grafo** | **graphify** | Análise estática da AST, grafo de conexões em `graphify-out/` e regras dedicadas |

---

## 3. Comandos Principais

| Ação | Comando | Descrição |
| :--- | :--- | :--- |
| **Iniciar Aplicação (Produção/Rede)** | `iniciar_servidor.bat` | Script mestre: ativa o `venv`, libera a porta 5000, configura regra de Firewall, detecta IP de rede e sobe o Waitress |
| **Iniciar Manualmente via Python** | `python app.py` | Executa o servidor WSGI Waitress em `0.0.0.0:5000` |
| **Ativar Ambiente Virtual (CMD)** | `venv\Scripts\activate.bat` | Ativa o ambiente virtual isolado no Windows Command Prompt |
| **Ativar Ambiente Virtual (PowerShell)**| `.\venv\Scripts\Activate.ps1` | Ativa o ambiente virtual isolado no Windows PowerShell |
| **Instalar Dependências** | `pip install -r requirements.txt` | Instala/atualiza todas as bibliotecas necessárias |
| **Atualizar Grafo Graphify** | `python scripts/atualizar_graphify.py` | Atualiza o mapa de código incrementalmente (`graphify . --update`) |
| **Consultar Conhecimento no Grafo** | `python -m graphify query "<pergunta>"` | Realiza consultas arquiteturais sobre o grafo semântico |
| **Testar Segurança e OAuth do GLPI**| `python scripts/testar_etapa3_seguranca.py` | Executa a suíte de validação de 5 pilares do cliente GLPI |
| **Testar Sincronização GLPI** | `python scripts/testar_glpi_sync.py` | Testa a rotina de importação de chamados do GLPI |
| **Popular Ramais Iniciais** | `python scripts/seed_ramais.py` | Popula o banco com os ramais corporativos cadastrados |
| **Criar Atalho no Desktop** | `criar_atalho_desktop.bat` | Cria atalho amigável no desktop do Windows para os operadores |

---

## 4. Variáveis de Ambiente (`.env`)

As variáveis devem ser configuradas no arquivo `.env` na raiz do projeto (baseando-se no `.env.example`). O arquivo `.env` contém credenciais e **NUNCA DEVE SER COMMITADO NO GIT**.

| Variável | Padrão / Exemplo | Finalidade |
| :--- | :--- | :--- |
| `SECRET_KEY` | *(Hash randômico de 64 hex)* | Assinatura de sessões e proteção CSRF |
| `FLASK_APP` | `app.py` | Ponto de entrada da aplicação Flask |
| `FLASK_ENV` | `production` / `development` | Ambiente de execução |
| `HOST` | `0.0.0.0` | IP de escuta (permite conexões de toda a rede local) |
| `PORT` | `5000` | Porta TCP do servidor web |
| `DATABASE_URL` | `sqlite:///chamados.db` | URI do banco SQLite unificado |
| `SESSION_COOKIE_SECURE` | `false` | Se `true`, cookies de sessão trafegam apenas sob HTTPS |
| `SNMP_COMMUNITY` | `public` | Comunidade SNMP para leitura das impressoras de rede |
| `SMTP_SERVER` | `smtp.office365.com` | Host do servidor de correio corporativo |
| `SMTP_PORT` | `587` | Porta SMTP com STARTTLS |
| `SMTP_USER` | `seu.email@empresa.com.br` | Usuário autenticador do envio |
| `SMTP_PASSWORD` | `********` | Senha ou App Password de envio de e-mails |
| `SMTP_USE_TLS` | `true` | Habilita criptografia TLS no transporte |
| `MAIL_FROM_ADDRESS` | `ti@empresa.com.br` | Endereço exibido no campo "De:" (Send As) |
| `MAIL_FROM_NAME` | `Departamento de TI` | Nome de exibição do remetente institucional |
| `GLPI_ENABLE_SYNC` | `true` / `false` | Ativa/desativa o worker agendado de sincronização GLPI |
| `GLPI_API_URL` | `https://helpdesk.empresa.com.br/api.php` | Endpoint base da API REST v2.3 do GLPI |
| `GLPI_CLIENT_ID` | `********` | Client ID da aplicação OAuth2 no GLPI |
| `GLPI_CLIENT_SECRET` | `********` | Client Secret da aplicação OAuth2 no GLPI |
| `GLPI_USERNAME` | `usuario_servico_glpi` | Conta de serviço para autenticação na API do GLPI |
| `GLPI_PASSWORD` | `********` | Senha da conta de serviço no GLPI |
| `GLPI_PROFILE_ID` | `4` | Perfil da API (4 = Super-Admin, visão corporativa total) |
| `GLPI_ENTITY_ID` | `0` | Entidade raiz no GLPI |
| `GLPI_ENTITY_RECURSIVE` | `true` | Expansão recursiva de entidades filhas |
| `GLPI_SYNC_INTERVAL_MINUTES`| `15` | Intervalo de polling da rotina em segundo plano |
| `GLPI_BATCH_SIZE` | `30` | Teto estrito de chamados consultados por ciclo |
| `GLPI_REQUEST_TIMEOUT` | `15` | Timeout em segundos para evitar retenção de threads |
| `GLPI_NF_CANCEL_EMAIL_RECIPIENT` | `gestao.ti@empresa.com.br` | Destinatário de alertas de cancelamento de NF (Form ID 36) |

---

## 5. Estrutura de Pastas e Arquivos

```text
central-chamados/
├── .agents/                          # Regras e workflows para agentes de IA
│   ├── rules/
│   │   └── graphify.md               # Regras obrigatórias de navegação e atualização do Graphify
│   └── workflows/
│       └── graphify.md               # Workflow do Graphify
├── 00-anything/                      # DIRETÓRIO OBRIGATÓRIO: isolamento de relatórios, drafts e specs
│   └── {sequencial} - {nome} {data}/ # Subpastas organizadas por demanda/implementação
├── assinaturasModelos/               # Modelos e assets gráficos de assinaturas institucionais
├── docs/                             # Guias arquiteturais detalhados
│   └── guia_integracao_email_outlook.md # Guia oficial de integração SMTP/Office 365
├── graphify-out/                     # Artefatos gerados pelo Graphify (grafo, wiki, métricas)
│   ├── graph.json                    # Grafo semântico da base de código
│   ├── GRAPH_REPORT.md               # Relatório executivo do grafo de arquitetura
│   └── wiki/index.md                 # Ponto de navegação estruturada gerado automaticamente
├── instance/                         # Diretório de instância do Flask
├── logs/                             # Logs de auditoria da aplicação com rotação
├── routes/                           # Blueprints do Flask (Camada de Apresentação / Rotas)
│   ├── __init__.py
│   ├── assinatura.py                 # Rotas do gerador de assinaturas de e-mail
│   ├── auth.py                       # Autenticação: login, logout, registro e aprovação
│   ├── base_conhecimento.py          # Wiki/KB: artigos, categorias, tags, busca e votação
│   ├── chamados.py                   # Gestão interna de chamados (CRUD, filtros e status)
│   ├── dashboard.py                  # Painel de métricas analíticas e estatísticas de chamados
│   ├── glpi_admin.py                 # Painel administrativo e gatilhos manuais de sincronização GLPI
│   ├── impressoras.py                # Gestão de impressoras, status SNMP e suprimentos
│   ├── itens_sala.py                 # Gestão de estoque e movimentações entre salas de TI
│   ├── main.py                       # Rota inicial e redirecionamentos
│   ├── ramais.py                     # Consulta, cadastro e edição do catálogo de ramais
│   └── usuarios.py                   # Gestão de usuários, perfis RBAC e aprovação de contas
├── services/                         # Camada de Negócio (Lógica, Cálculos e Integrações)
│   ├── assinatura_service.py         # Geração de HTML e renderização de assinaturas
│   ├── chamado_service.py            # Regras operacionais de chamados
│   ├── conhecimento_service.py       # Serviços da Base de Conhecimento (score, filtros, markdown)
│   ├── email_service.py              # Módulo de despacho de e-mails corporativos via SMTP
│   ├── glpi_sync.py                  # Rotina de sincronização de chamados GLPI (Política Carga Zero)
│   ├── impressoras_services.py       # Orquestração de status e atualização de suprimentos
│   ├── itens_sala_service.py         # Controle transacional de movimentação de itens e relatórios PDF
│   ├── snmp_service.py               # Driver SNMP de polling de hardware de impressoras
│   ├── suprimentos_services.py       # Regras de movimentação de estoque de suprimentos
│   └── usuario_service.py            # Validação e hierarquia de usuários
├── static/                           # Assets estáticos servidos pelo Flask
│   ├── css/                          # Folhas de estilo da aplicação
│   ├── fonts/                        # Tipografias locais
│   ├── icons/                        # Ícones e favicons
│   ├── img/                          # Imagens e logotipos institucionais
│   ├── manifest.json                 # Manifesto PWA
│   └── sw.js                         # Service Worker para suporte offline
├── templates/                        # Templates Jinja2 (Server-Side Rendering)
│   ├── base.html                     # Layout mestre: navbar, sidebar, flash messages e scripts
│   ├── dashboard.html                # Painel de indicadores com gráficos
│   ├── index.html                    # Página inicial / portal de acesso
│   ├── offline.html                  # Tela de fallback para conectividade offline
│   ├── assinatura/                   # Views do gerador de assinatura de e-mail
│   ├── auth/                         # Views de login, cadastro e status de aprovação
│   ├── chamados/                     # Views de listagem, abertura e detalhamento de tickets
│   ├── conhecimento/                 # Views da Base de Conhecimento (artigos, busca, editor)
│   ├── glpi/                         # Views de monitoramento da sincronização GLPI
│   ├── impressoras/                  # Views do mapa de impressoras e controle de suprimentos
│   ├── itens_sala/                   # Views de inventário e transferências de itens de TI
│   ├── ramais/                       # Views do catálogo telefônico interno
│   └── usuarios/                     # Views administrativas de controle de usuários e RBAC
├── utils/                            # Utilitários transversais
│   ├── decorator.py                  # Decorators de controle de acesso RBAC (@admin_required, etc.)
│   ├── glpi_client.py                # Cliente HTTP para a API do GLPI (OAuth2, Circuit Breaker)
│   └── logger.py                     # Configuração centralizada de logs com rotação
├── scripts/                          # Scripts operacionais e de manutenção
│   ├── atualizar_graphify.py         # Atualizador do Graphify via Python
│   ├── criar_atalho_desktop.ps1      # PowerShell helper para atalhos
│   ├── get_ip.py                     # Detector de IP de rede local
│   ├── migrar_bancos.py              # Script de migração de schemas do banco SQLite
│   ├── migrate_glpi_fields.py        # Migração incremental de colunas de rastreabilidade GLPI
│   ├── seed_ramais.py                # População de dados padrão de ramais
│   ├── testar_etapa3_seguranca.py    # Suíte de validação de segurança do cliente GLPI
│   └── testar_glpi_sync.py           # Teste funcional de sincronização GLPI
├── tests/                            # Testes automatizados funcionais e de integração
├── venv/                             # Ambiente virtual Python isolado
├── .env                              # Variáveis de ambiente reais (IGNORADO PELO GIT)
├── .env.example                      # Template seguro de variáveis de ambiente
├── .gitignore                        # Regras de exclusão do Git
├── app.py                            # Ponto de entrada da aplicação, configuração e scheduler
├── criar_atalho_desktop.bat          # Batch script para criar atalho no Windows
├── iniciar_servidor.bat              # Batch script oficial de inicialização em rede
├── Login-RBAC.md                     # Especificação técnica do sistema de Login e RBAC
├── models.py                         # Definição unificada dos modelos de dados SQLAlchemy
└── requirements.txt                  # Lista de dependências Python com versões fixadas
```

### 5.1 Arquivos Ponteiro Multi-IA (Zero Duplicação de Regras)
Para garantir que qualquer IA (Claude Code, Gemini CLI, Cursor, Copilot) acesse a fonte da verdade sem duplicação de regras:

* **`CLAUDE.md`** (para Claude Code / Claude Desktop):
  ```markdown
  > Consulte integralmente as diretrizes arquiteturais, stack técnica, regras operacionais e convenções em [AGENTS.md](./AGENTS.md).
  ```
* **`GEMINI.md`** (para Gemini CLI / Code Assist):
  ```markdown
  > Consulte integralmente as diretrizes arquiteturais, stack técnica, regras operacionais e convenções em [AGENTS.md](./AGENTS.md).
  ```
* **`.github/copilot-instructions.md`** (para GitHub Copilot Chat):
  ```markdown
  > Consulte integralmente as diretrizes arquiteturais, stack técnica, regras operacionais e convenções em [AGENTS.md](../../AGENTS.md).
  ```

---

## 6. Arquitetura e Fluxo de Dados

A aplicação opera sob o padrão arquitetural **MVC / Layered Service-Oriented Architecture** com renderização no servidor (SSR):

```text
Requisição do Navegador / Rede Local (Porta 5000)
    │
    ▼
Waitress WSGI Server (Pool de 8 Threads Concorrentes)
    │
    ▼
Flask Application (app.py)
    ├─ setup_logging (Auditoria em logs/)
    ├─ load_dotenv (.env)
    ├─ PRAGMA SQLite (WAL mode, busy_timeout=30s)
    ├─ Flask-Login (load_user e verificar_usuario_ativo em before_request)
    ├─ CSRFProtect (Validação em todos os métodos inseguros POST/PUT/DELETE)
    │
    ├─ Blueprints (routes/):
    │    ├─ auth_bp           --> Autenticação, registro, aprovações
    │    ├─ chamados_bp       --> Tickets internos e ciclo de vida
    │    ├─ dashboard_bp      --> Indicadores e consolidação analítica
    │    ├─ impressoras_bp    --> Monitoramento de rede e suprimentos
    │    ├─ itens_sala_bp     --> Estoque distribuído entre salas
    │    ├─ conhecimento_bp   --> Base de Conhecimento e tutoriais
    │    ├─ ramais_bp         --> Catálogo telefônico corporativo
    │    ├─ glpi_admin_bp     --> Controle de sincronização GLPI
    │    ├─ assinatura_bp     --> Assinaturas de e-mail padronizadas
    │    └─ usuarios_bp       --> RBAC e gestão hierárquica
    │
    ├─ Camada de Serviços (services/):
    │    ├─ ImpressorasService / SnmpService (Comunicação de rede com impressoras)
    │    ├─ GlpiSync / GlpiClient (Consumo controlado de API externa com Circuit Breaker)
    │    ├─ ItensSalaService (Transações atômicas de movimentação e PDFs)
    │    ├─ ConhecimentoService (Cálculo de relevância e parser Markdown)
    │    └─ EmailService (Despacho SMTP via Microsoft 365)
    │
    ├─ Banco de Dados Unificado (chamados.db via models.py):
    │    └─ SQLAlchemy ORM (15 tabelas mapeadas com integridade referencial)
    │
    ├─ after_request: Injeção de Cabeçalhos de Segurança (nosniff, SAMEORIGIN, etc.)
    │
    ▼
Resposta HTML (Jinja2 Templates) / JSON APIs / Download de PDFs
```

### Orquestração em Segundo Plano (APScheduler):
O `app.py` instancia um `BackgroundScheduler` que executa independentemente da thread web:
1. `tarefa_atualizar_impressoras`: Executada a cada 1 hora para renovar métricas de toner, contadores de páginas e status das impressoras de rede.
2. `tarefa_sincronizar_glpi`: Executada a cada 15 minutos (configurável via `GLPI_SYNC_INTERVAL_MINUTES`) para sincronizar novos tickets do GLPI sob política de **Carga Zero**.
3. `tarefa_atualizar_graphify`: Executada a cada 6 horas para manter o grafo de conhecimento e dependências atualizado.

---

## 7. Modelo de Dados e Estado (`models.py`)

Todas as tabelas residem no banco SQLite unificado gerenciado por SQLAlchemy:

| Tabela | Classe Modelo | Descrição e Finalidade |
| :--- | :--- | :--- |
| `usuarios` | `Usuario` | Contas de usuário, senhas hash, perfis RBAC (`supremo`, `admin`, `operador`, `tecnicoImpressora`, `usuario`), status (`ativo`, `pendente`, `bloqueado`) e método hierárquico `pode_gerenciar()`. |
| `chamados` | `Chamado` | Tickets de suporte internos e importados. Contém solicitante, setor, categoria, prioridade, status, técnico atribuído, origem (`local` ou `glpi`) e campos de rastreabilidade `glpi_id` e `glpi_numero`. |
| `glpi_sync_logs` | `GlpiSyncLog` | Auditoria de execuções do sincronizador GLPI, contadores de tickets, status do ciclo, cursor de último ticket importado e mensagens de erro. |
| `impressoras` | `Impressora` | Cadastro de impressoras de rede (IP, nome, modelo, andar, sala, contato, MAC, serial, fabricante). Armazena níveis de toner (preto, ciano, magenta, amarelo), cilindro, papel, páginas impressas, status SNMP detalhado e flag `necessita_atencao`. |
| `estoque_suprimentos` | `EstoqueSuprimento` | Famílias de insumos compatíveis (ex: TN-3472, Lexmark MS810), saldo de toners, saldo de cilindros e estoque mínimo de segurança. |
| `historico_suprimentos`| `HistoricoSuprimento` | Registro imutável de entradas, saídas e trocas de suprimentos, vinculadas a impressora específica ou a ajuste de setor, com usuário responsável e data. |
| `kb_categorias` | `KbCategoria` | Categorias temáticas da Base de Conhecimento (slug, ícone Bootstrap, descrição e ordem de exibição). |
| `kb_tags` | `KbTag` | Etiquetas de busca e indexação de artigos. |
| `kb_artigo_tags` | `artigo_tags` | Tabela de relacionamento many-to-many entre artigos e tags. |
| `kb_artigos` | `KbArtigo` | Artigos técnicos completos em Markdown (`conteudo_md`), status (`publicado`, `rascunho`, `arquivado`), autor, visualizações, votos úteis/inúteis e pontuação ponderada de relevância. |
| `kb_feedbacks` | `KbFeedback` | Votos 👍/👎 de usuários com comentários opcionais de melhoria para artigos. |
| `kb_solicitacoes` | `KbSolicitacao` | Pedidos de criação de novos procedimentos/artigos enviados por colaboradores comuns, com fluxo de aprovação e resposta por administradores. |
| `itens_sala` | `ItemSala` | Itens de infraestrutura e periféricos da TI (cabos, mouses, teclados, adaptadores, memórias), estoque mínimo e unidade de medida. |
| `itens_sala_estoque` | `ItemSalaEstoque` | Saldo físico segregado por sala (`Sala Principal` e `Sala TI - 3º Andar`) com constraint única por `item_id + sala`. |
| `itens_sala_movimentacoes`| `ItemSalaMovimentacao`| Histórico auditado de movimentações (`entrada`, `saida`, `transferencia`, `ajuste`), salas de origem/destino, responsável técnico e solicitante. |
| `ramais` | `Ramal` | Diretório telefônico corporativo: nome do colaborador, departamento/setor, número do ramal e andar. |

---

## 8. Regras de Negócio Fundamentais

### 8.1 Hierarquia Estrita de Usuários e RBAC
* **Administrador Supremo (`admin@king.com` ou perfil `supremo`)**:
  - Detém poder irrestrito no sistema.
  - É o único que pode aprovar, redefinir senhas, alterar perfis e desativar contas de outros Administradores.
* **Administrador Comum (`admin`)**:
  - Gerencia operadores, técnicos e usuários comuns.
  - **NÃO PODE** alterar, redefinir senhas ou desativar o Administrador Supremo.
  - **NÃO PODE** alterar dados ou senhas de outros Administradores.
  - Pode gerenciar sua própria conta.
* **Técnico de Impressoras (`tecnicoImpressora`)**:
  - Acesso liberado aos módulos de impressoras, estoque de suprimentos e histórico de trocas.
  - Bloqueado de gerenciar usuários, chamados administrativos ou configurações do sistema.
* **Operador (`operador`)**:
  - Atende e atualiza chamados, gerencia estoque e itens de sala, cria artigos na Base de Conhecimento.
* **Usuário Comum (`usuario`)**:
  - Abre e acompanha seus próprios chamados, consulta a Base de Conhecimento (e envia solicitações de artigos), pesquisa ramais e gera sua assinatura de e-mail.

### 8.2 Política "Carga Zero" na Sincronização GLPI
* **Autenticação em Cache**: O token JWT OAuth2 da API do GLPI é armazenado em memória com timestamp de expiração. Zero requisições extras de login durante a vida útil do token.
* **Lote Estrito (`GLPI_BATCH_SIZE = 30`)**: Nenhuma busca ao GLPI pode retornar volumes descontrolados que degradem o servidor de produção da organização.
* **Circuit Breaker**: Em caso de falhas consecutivas de rede ou instabilidade no endpoint do GLPI, o circuito é aberto automaticamente para proteger os recursos locais e remotos.
* **Idempotência**: Chamados importados possuem `glpi_id` único no banco local; chamados repetidos são ignorados silenciosamente sem duplicações.
* **Notificação de Cancelamento de NF**: Chamados identificados com o formulário específico de cancelamento de NF (Form ID 36) disparam automaticamente e-mail institucional formatado para o setor responsável de aprovação.

### 8.3 Movimentação Atômica de Itens entre Salas de TI
* Toda transferência de item entre a **Sala Principal** e a **Sala TI - 3º Andar** deve ser executada dentro de um bloco de transação atômica (`db.session.begin_nested()` ou `commit/rollback`).
* É terminantemente proibido deduzir saldo da sala de origem sem incrementar instantaneamente a sala de destino.
* Transferências exigem identificação de quem entregou (técnico) e quem recebeu.

### 8.4 Monitoramento Inteligente de Impressoras (SNMP)
* Filas virtuais de software (PDF24, Microsoft Print to PDF, OneNote, AnyDesk) são filtradas pela property `is_virtual` e ignoradas nas rotinas de alerta de hardware.
* O cálculo de percentual de suprimentos pondera nível atual contra o nível máximo suportado pelo cartucho físico reportado pelo fabricante.
* **Ordenação Física por Andar**: A listagem de impressoras (Página 1: Online e Página 2: Offline) é ordenada hierarquicamente por andar via `ImpressorasService.get_criterio_ordenacao_andar()` no SQLAlchemy, priorizando: -1 (Subsolo) → Térreo → 1º Andar → 2º Andar → 3º Andar → Unidades Externas/Filiais → Não Informados, com desempate secundário por nome.
* **Alternância de Visualização Desktop (Lista / Cards)**: O operador no desktop pode alternar dinamicamente entre visualização em tabela clássica e visualização em cards responsivos (2 a 3 colunas) através de controles dedicados no cabeçalho. A preferência é memorizada no navegador via `localStorage` (`hub_impressoras_view_mode`) com inicialização síncrona anti-flicker e animação de transição, mantendo o mobile sempre otimizado em cards.

---

## 9. Convenções de Código e Boas Práticas

* **Python e Estilo**:
  - Aderência rigorosa à **PEP 8**.
  - Funções e métodos com nomes expressivos em português ou inglês padronizado (`buscar_tickets`, `calcular_percentual`).
  - Utilização de `logger.info`, `logger.warning`, `logger.error` em vez de `print()` puro para rastreabilidade em arquivos de log.
* **Camada de Apresentação (Routes) vs Serviços (Services)**:
  - **Rotas (`routes/`)**: Devem ser limpas e concisas. Responsáveis apenas por receber requisições HTTP, autenticar decorators, validar inputs básicos, acionar a camada de serviço correspondente e renderizar o template Jinja2 ou retornar JSON.
  - **Serviços (`services/`)**: Centralizam todas as regras de negócio, integrações externas (SNMP, GLPI, SMTP), cálculos matemáticos e regras de transação no banco de dados.
* **Segurança e Banco de Dados**:
  - **Proibido SQL puro concatenado**: Sempre utilize o ORM SQLAlchemy ou queries parametrizadas com bind parameters (`:param`) para blindagem total contra SQL Injection.
  - **Transações Seguras**: Em operações que envolvem múltiplas tabelas, use blocos `try/except` garantindo `db.session.rollback()` em falhas.
  - **CSRF Tokens em Formulários**: Todo formulário HTML POST **DEVE** incluir obrigatoriamente a tag `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>`.
* **Templates Jinja2**:
  - Todo template deve estender `base.html` com os blocos adequados: `{% extends "base.html" %}`, `{% block title %}`, `{% block content %}`, `{% block scripts %}`.
  - Use filtros seguros do Jinja2 e escape automático para dados de usuários (prevenção de XSS).

---

## 10. Estratégia de Testes

* **Testes de Integração e Segurança Existentes**:
  - `python scripts/testar_etapa3_seguranca.py`: Valida os 5 pilares de segurança do cliente GLPI (OAuth2, cache de token em memória, respeito ao batch size, ausência de dados sensíveis em logs e disparo do Circuit Breaker).
  - `python scripts/testar_glpi_sync.py`: Valida o pipeline de importação de chamados do GLPI.
* **Testes Unitários e Funcionais**:
  - Testes de rotas e serviços devem ser estruturados dentro de `tests/`.
  - Execução via `pytest` ou `python -m unittest discover tests`.
* **Quando é obrigatório rodar/criar testes**:
  - Alterações nos decorators de segurança RBAC (`utils/decorator.py`).
  - Modificações na camada de integração do GLPI ou SNMP.
  - Ajustes em lógicas transacionais de movimentação de estoque ou transferências entre salas.

---

## 11. Estratégia de Segurança (SAST, Concorrência & Higiene de Segredos)

| Vetor de Segurança | Mecanismo Adotado no Projeto |
| :--- | :--- |
| **CSRF (Cross-Site Request Forgery)** | `Flask-WTF` com `CSRFProtect(app)` ativo globalmente. Formulários sem token CSRF são bloqueados com HTTP 400. |
| **XSS & Content Sniffing** | Cabeçalhos HTTP injetados em `@app.after_request`: `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection: 1; mode=block`. |
| **Proteção de Sessão** | `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`, e `SESSION_COOKIE_SECURE` conforme ambiente. Sessão não persistente (`SESSION_PERMANENT = False`). |
| **Auditoria e Bloqueio em Tempo Real** | O hook `@app.before_request` checa se o usuário logado continua com `status == 'ativo'` no banco. Se for desativado por um admin, sua sessão é derrubada instantaneamente. |
| **Concorrência e Lock de Banco (SQLite)** | Executado com `PRAGMA journal_mode=WAL` e `busy_timeout=30000`, permitindo leituras simultâneas sem bloqueio enquanto transações de escrita ocorrem em fila controlada. |
| **Higiene de Segredos** | Credenciais sensíveis (OAuth GLPI, senhas SMTP, chaves secretas) residem estritamente em `.env` e nunca são versionadas no Git. |

---

## 12. Cuidados e Armadilhas Comuns

1. **Esquecer o token CSRF**: Criar formulários HTML POST sem `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>` causará erro imediato `400 Bad Request: CSRF token missing`.
2. **Concorrência SQLite e Waitress**: Como o Waitress opera com 8 threads simultâneas, nunca remova os parâmetros `timeout=30`, `check_same_thread=False` ou os pragmas `WAL` do SQLAlchemy; sem eles, requisições simultâneas podem disparar `sqlite3.OperationalError: database is locked`.
3. **Ignorar a Hierarquia do Supremo**: Nunca permita que um Administrador comum altere perfil, status ou senha de outro Administrador ou do Administrador Supremo (`admin@king.com`). Respeite sempre a validação `usuario.pode_gerenciar(alvo)`.
4. **Chamadas Bloqueantes na Thread Web**: Rotas web nunca devem executar varreduras lentas de rede SNMP em dezenas de impressoras sincronicamente. A leitura pesada deve ser delegada aos workers do scheduler ou feita com limites e timeouts estritos.
5. **Arquivos soltos na raiz**: Nunca salve drafts, specs, notas ou relatórios de subagentes/EGM na raiz. Use sempre `00-anything/{sequencial} - {nome} {data}/`.
6. **Esquecer de atualizar o AGENTS.md e o graphify**: Finalizar uma alteração estrutural sem documentar neste arquivo e sem rodar `graphify update .` quebra a continuidade de trabalho para futuros agentes de IA.

---

## 13. Checklist para Agentes ao Finalizar Tarefas

Antes de considerar qualquer tarefa como concluída, o agente DEVE verificar:

* [ ] **Isolamento de artefatos na raiz**: Nenhum rascunho, spec, teste temporário ou relatório EGM solto na raiz do repositório (todos salvos dentro de `00-anything/{sequencial} - {nome} {data}/`).
* [ ] **Compatibilidade arquitetural**: Nenhum código alheio à stack real (Python/Flask/Jinja2/SQLite) inserido.
* [ ] **Proteção CSRF garantida**: Formulários novos contêm o campo `csrf_token`.
* [ ] **Controle de acesso RBAC verificado**: Rotas protegidas pelos decorators pertinentes (`@login_required`, `@admin_required`, `@printer_staff_required`, `@supremo_required`).
* [ ] **Integridade transacional**: Modificações no banco utilizam `try/except` com `db.session.rollback()` em caso de exceções.
* [ ] **Sincronização com o Graphify realizada**: `graphify update .` ou `python scripts/atualizar_graphify.py` executado sem erros.
* [ ] **Segurança de credenciais**: Zero tokens, senhas ou credenciais expostas no código-fonte; variáveis novas devidamente documentadas no `.env.example`.
* [ ] **Estrutura de pastas da Seção 5 atualizada** caso arquivos ou rotas tenham sido adicionados/removidos.
* [ ] **Este arquivo `AGENTS.md` atualizado** refletindo as mudanças estruturais aplicadas.
* [ ] **Nova entrada registrada na tabela de Histórico de alterações deste arquivo** abaixo.
* [ ] **Git**: Branch dedicada criada, commits atômicos semânticos aplicados e push enviado ao GitHub (`git push -u origin <branch>`).

---

## 📜 Histórico de alterações deste arquivo

| Data | Responsável | Alteração Realizada |
| :--- | :--- | :--- |
| 2026-11-03 | Agente IA | Criação inicial do modelo base `AGENTS.md` para novos projetos. |
| 2026-11-04 | Agente IA | Adição de regras obrigatórias de decomposição de tarefas em issues, testes funcionais Playwright e SAST. |
| 2026-11-07 | Agente IA | Adição de isolamento de relatórios em `00-anything/`, regra anti-alucinação e dependência obrigatória do `graphify`. |
| 2026-11-10 | Antigravity AI | **Instanciação Oficial no Projeto `central-chamados`**: Cópia do modelo base e adaptação integral para a realidade do **Hub Central - SirReinato Brasfort** (Python 3.10+, Flask 3.1, Jinja2, Waitress multi-thread, SQLite em modo WAL, RBAC com Admin Supremo, APScheduler, PySNMP, integração segura com GLPI API v2.3 sob política de Carga Zero, controle de itens entre salas de TI, Base de Conhecimento, diretório de ramais e gerador de assinaturas). |
| 2026-11-10 | Antigravity AI | **Otimização de UX Mobile da Base de Conhecimento**: Refatoração de `templates/conhecimento/index.html` (Hero compacto, barra de busca responsiva, botões de ação fluidos em linha única, carrossel de chips com scroll suave) e `templates/conhecimento/artigo.html` (paddings laterais reduzidos para ganho de área de leitura, correção de string literal "None", inclusão de Sumário/ToC retrátil no topo do mobile, feedback touch-friendly) e novas media queries dedicadas em `static/css/global.css`. |
| 2026-11-10 | Antigravity AI | **Otimização de UX Mobile de Impressoras e Estoque de Suprimentos**: Implementação de visualização híbrida responsiva (desktop em tabela completa, telas < 992px em cards `.cardImpressoraMobile` e `.cardEstoqueFamilia` com barras de progresso semânticas para níveis de toner e cilindro, botões touch-friendly para "Editar / Contador" e "Retirar Insumo", histórico de movimentações em cards timeline compactos `.cardHistoricoMobile` e modais compartilhados sem duplicação de IDs no DOM). |
| 2026-11-11 | Antigravity AI | **Alternância Lista/Cards no Desktop e Ordenação por Andar de Impressoras**: Implementação de ordenação física hierárquica por andar (-1/Subsolo, Térreo, 1º, 2º, 3º, Outras Unidades e Não Informados) via `ImpressorasService.get_criterio_ordenacao_andar()` no SQLAlchemy (`services/impressoras_services.py`), novo seletor visual Lista ↔ Cards no cabeçalho desktop (`.seletorVisualizacaoImpressoras`), grid responsivo multi-colunas para desktop, persistência da preferência em `localStorage` (`hub_impressoras_view_mode`), inicialização síncrona anti-flicker e animação de transição suave em `templates/impressoras/impressoras.html` e `static/css/global.css`. |
