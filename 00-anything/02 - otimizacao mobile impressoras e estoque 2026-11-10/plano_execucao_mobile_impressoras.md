# Plano de Execução — Otimização Mobile para Impressoras e Estoque de Suprimentos

**Data:** 2026-11-10  
**Branch:** `feature/mobile-impressoras-estoque`  
**Escopo:** `templates/impressoras/impressoras.html`, `templates/impressoras/estoque.html`, `static/css/global.css`, `AGENTS.md`  

---

## 1. Diagnóstico do Problema Mobile Atual
1. **`impressoras.html`**:
   - A tabela desktop (`.tabelaPadrao`) possui 9 colunas largas: Nome, IP/Rede, Localização, Status, Toner, Cilindro, Suprimento, Última Verificação, Ações.
   - Na tela mobile (~360px a 430px de largura), a tabela fica truncada horizontalmente, forçando scroll horizontal indesejado ou cortando status, porcentagens de toner e cilindro, e botões de ação (como visto na imagem anexada pelo usuário).
   - O cabeçalho e métricas superiores ocupam bastante espaço vertical e as ações em lote precisam de boa usabilidade ao toque.

2. **`estoque.html`**:
   - A coluna de "Saldos Atuais em Estoque" e a tabela inferior de "Histórico de Movimentações" usam tabelas com várias colunas que no mobile quebram ou exigem scroll lateral.
   - No mobile, a exibição de cada família de suprimento em um **Card de Estoque** (com saldo de toner, cilindro, alerta de estoque mínimo e botões de ação direta: "Repor", "Ajustar", "Ver Impressoras") é infinitamente superior e amigável ao operador em campo.
   - O histórico de movimentações pode ter versão compacta em timeline/card para visualização imediata no celular.

---

## 2. Solução Arquitetural Proposta

### A. Impressoras (`impressoras.html`):
- **Abordagem Híbrida Inteligente (Zero Regressão Desktop)**:
  - No Desktop/Tablet (`d-none d-lg-block`): mantém a tabela rica e detalhada existente intacta.
  - No Mobile (`d-lg-none`): renderiza uma lista de **Cards de Impressora Mobile** (`.cardImpressoraMobile`):
    - **Header do Card**:
      - Ponto de status pulsante (Online / Offline) + Nome do equipamento em destaque.
      - Badge de Virtual / S/N serial.
    - **Corpo do Card**:
      - **Linha de Conexão & Local**: IP clicável / Badge Manual + Ícone de localização (Andar - Sala ou Local).
      - **Barras de Nível de Suprimentos Touch**:
        - Barra de progresso para Toner Preto com cor semântica (Verde > 25%, Amarelo <= 25%, Vermelho <= 15%).
        - Barra de progresso para Cilindro (se disponível).
      - **Metadados rápidos**: Suprimento vinculado (família com badge) + Contador de páginas impressas (se houver).
    - **Footer / Ações do Card**:
      - Botão "Editar / Contador" (abre modal de edição).
      - Botão "Retirar Insumo" (abre modal de retirada).
      - Se tiver IP: link direto ou botão para abrir a interface web do equipamento.

### B. Estoque de Suprimentos (`estoque.html`):
- **Saldos de Famílias em Cards Mobile**:
  - No Mobile (`d-lg-none`): cards individuais para cada família (`.cardEstoqueFamilia`):
    - Nome da família + badge de "Estoque Baixo" se atingir mínimo.
    - Grid visual com 2 medidores: **Toner** (quantidade em estoque vs mínimo) e **Cilindro** (quantidade em estoque vs mínimo).
    - Ações rápidas em botões de largura total ou grid 3 colunas: [➕ Repor], [⚙️ Ajustar], [🖨️ Impressoras].
- **Histórico de Movimentações Mobile**:
  - Cards de auditoria com data/hora, tipo de movimentação (Entrada/Saída), insumo, setor de destino e operador responsável.

### C. Estilos Globais (`static/css/global.css`):
- Definição de classes dedicadas:
  - `.cardImpressoraMobile`, `.cardImpressoraMobileHeader`, `.cardImpressoraMobileBody`, `.cardImpressoraMobileFooter`.
  - `.barraProgressoInsumo`, `.barraProgressoInsumoFill`.
  - `.cardEstoqueFamilia`, `.cardHistoricoMobile`.
  - Media queries finas para telas menores que 576px e 768px.

---

## 3. Divisão de Tarefas / Issues
1. **SIR-80**: `feat(impressoras): implementar visualização em cards responsivos para mobile em impressoras.html`
2. **SIR-81**: `feat(estoque): criar cards responsivos para saldos e histórico de movimentações em estoque.html`
3. **SIR-82**: `style(impressoras): adicionar estilos modernos de cards e controles touch-friendly em global.css`
4. **SIR-83**: `docs(impressoras): registrar melhorias de UX mobile no histórico do AGENTS.md e atualizar graphify`
