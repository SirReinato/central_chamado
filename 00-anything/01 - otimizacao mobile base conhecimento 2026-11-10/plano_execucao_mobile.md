# Plano de Execução — Otimização Mobile da Base de Conhecimento (index.html e artigo.html)

**Data**: 2026-11-10  
**Branch**: `feature/mobile-conhecimento`  
**Issues Linear**: [SIR-76](https://linear.app/sirreinato/issue/SIR-76), [SIR-77](https://linear.app/sirreinato/issue/SIR-77), [SIR-78](https://linear.app/sirreinato/issue/SIR-78), [SIR-79](https://linear.app/sirreinato/issue/SIR-79)  
**Objetivo**: Maximizar o aproveitamento da área útil de tela em dispositivos móveis, reduzir espaço vertical desperdiçado antes dos artigos, compactar controles e melhorar a legibilidade.

---

## Diagnóstico das Telas Atuais (Baseado nas Evidências Visuais)

### 1. `templates/conhecimento/index.html` (Screenshot 1)
- **Hero Container Descomunal**:
  - `padding: 32px 28px` com altura total consumindo ~65% da tela do celular.
  - Título `h1` em 1.85rem com margem grande.
  - Parágrafo descritivo de 4 linhas empurrando a busca para baixo.
  - 3 botões empilhados verticalmente ("Sugerir Conteúdo", "Minhas Solicitações", "Painel Admin") ocupando quase 160px de altura só para ações secundárias.
  - A barra de busca tem 50px de altura com 24px de margem superior.
- **Barra de Categorias**:
  - Chips com padding generoso e sem efeito de scroll mobile otimizado.
- **Barra de Controle (Contador, Ordenação e Grid/List)**:
  - Ocupa outra fatia inteira da tela antes do primeiro card.
- **Resultado Negativo**: O usuário é forçado a dar 2 scrolls inteiros para conseguir ler o título do primeiro artigo.

### 2. `templates/conhecimento/artigo.html` (Screenshot 2)
- **Padding do Artigo Excessivo**:
  - `.kbArticleContainer` possui `padding: 36px 40px`. Em telas de 360-400px de largura, 80px é desperdiçado em margens pretas/laterais.
- **Ações do Topo**:
  - Botões ("Copiar Link", "Editar Artigo", "Voltar") ocupam muito espaço no topo.
- **Bug da String "None"**:
  - O campo `artigo.resumo` quando vazio ou nulo está renderizando como string literal `"None"` logo abaixo do título do artigo.
- **Cabeçalho & Metadados**:
  - Badge de categoria, leitura e visualizações ficam desordenados e ocupam muitas linhas verticais.
  - Título com fonte 2rem quebra em 4 linhas desnecessariamente.
- **Navegação de Tópicos (ToC)**:
  - No mobile, o sumário de navegação de tópicos cai para o fim da página (após todo o artigo), perdendo sua utilidade de navegação rápida.

---

## Soluções de Design e Engenharia Propostas

1. **`index.html` (Hero Compacto e Responsivo)**:
   - Em telas móveis (`@media (max-width: 768px)`):
     - Padding do Hero reduzido para `16px 14px`.
     - Título compacto em 1.35rem e descrição reduzida ou em linha sutil.
     - Botões de ação secundária reorganizados em barra de botões com ícones compactos (`btn-group` ou flex horizontal com textos curtos e badges).
     - Barra de busca integrada com altura 42px.
     - Barra de controle de ordenação e visualização compactada.
     - Cards de artigos com padding otimizado (14px 14px) para visualização rápida.

2. **`artigo.html` (Leitura Imersiva e Otimizada)**:
   - Padding do container reduzido para `16px 12px` no mobile (ganho imediato de +50px de largura útil para o texto).
   - Título ajustado para `1.35rem` com `line-height: 1.3`.
   - Correção do `artigo.resumo`: exibir apenas se `artigo.resumo and artigo.resumo.strip() and artigo.resumo != 'None'`.
   - Inserção de Sumário Retrátil (*Accordion / Collapse* "📑 Ver Tópicos do Artigo") no topo exclusivo para mobile quando houver cabeçalhos no Markdown.
   - Barra de ações superior unificada e compacta.
   - Feedback box alinhada para toque fácil com botões em `flex: 1`.

3. **`static/css/global.css`**:
   - Criação de bloco completo e dedicado de regras responsivas sob `@media (max-width: 768px)` e `@media (max-width: 576px)`.

---

## Status Final da Execução (DoD Validado)

| Issue | Escopo | Status |
| :--- | :--- | :--- |
| **SIR-76** | Otimização do Hero e Listagem de Artigos (`index.html`) | ✅ Concluído (Done) |
| **SIR-77** | Layout de Leitura, Sumário Retrátil e Correção do `"None"` (`artigo.html`) | ✅ Concluído (Done) |
| **SIR-78** | Regras Responsivas Avançadas em `global.css` (<768px e <576px) | ✅ Concluído (Done) |
| **SIR-79** | Rastreabilidade no `AGENTS.md`, Sincronização Graphify e Git Push | ✅ Concluído (Done) |

### Resultados Obtidos:
- **Área útil de visualização no `index.html`**: Redução de ~140px de altura no cabeçalho. Artigos agora aparecem imediatamente no primeiro terço da tela do smartphone.
- **Área de leitura no `artigo.html`**: Ganho de +50px de largura útil (padding reduzido de 40px para 10-12px em telas estreitas).
- **Bug do `"None"`**: 100% eliminado em artigos com resumo nulo/vazio.
- **Sumário Mobile**: Adicionado accordion colapsável para saltos rápidos no conteúdo longo.

