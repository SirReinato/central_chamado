import re
import unicodedata
from datetime import datetime
import markdown
from models import db, KbCategoria, KbTag, KbArtigo, KbFeedback, KbSolicitacao, Usuario

class ConhecimentoService:
    @staticmethod
    def gerar_slug(texto):
        """Converte texto para formato slug URL amigável."""
        if not texto:
            return ""
        # Normaliza caracteres acentuados
        texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8')
        texto = re.sub(r'[^\w\s-]', '', texto).strip().lower()
        slug = re.sub(r'[-\s]+', '-', texto)
        return slug or "artigo"

    @staticmethod
    def calcular_tempo_leitura(conteudo_md):
        """Calcula o tempo estimado de leitura (baseado em ~180 palavras/min)."""
        if not conteudo_md:
            return 1
        palavras = len(re.findall(r'\w+', conteudo_md))
        minutos = max(1, int(round(palavras / 180)))
        return minutos

    @classmethod
    def renderizar_markdown(cls, conteudo_md):
        """
        Converte Markdown para HTML seguro, com suporte a realce de código,
        tabelas, sumário (ToC) e alertas estilo GitHub (> [!NOTE], etc.).
        """
        if not conteudo_md:
            return "", ""

        # Pré-processa alertas estilo GitHub (> [!NOTE] -> admonitions)
        conteudo_processado = cls._preprocessar_callouts_github(conteudo_md)

        md = markdown.Markdown(extensions=[
            'fenced_code',
            'tables',
            'nl2br',
            'toc'
        ])
        html = md.convert(conteudo_processado)
        toc = getattr(md, 'toc', '')

        return html, toc

    @staticmethod
    def _preprocessar_callouts_github(texto):
        """
        Substitui blocos estilo GitHub:
        > [!NOTE]
        > Mensagem
        Por HTML estilizado compatível com o tema.
        """
        padrao = r'>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*\n((?:>.*\n?)*)'

        def substituir_callout(match):
            tipo = match.group(1).upper()
            linhas = match.group(2).split('\n')
            corpo = '<br>'.join([re.sub(r'^>\s?', '', l) for l in linhas if l.strip()])

            classes = {
                'NOTE': ('calloutKbNote', 'bi-info-circle-fill', 'Informação'),
                'TIP': ('calloutKbTip', 'bi-lightbulb-fill', 'Dica'),
                'IMPORTANT': ('calloutKbImportant', 'bi-exclamation-circle-fill', 'Importante'),
                'WARNING': ('calloutKbWarning', 'bi-exclamation-triangle-fill', 'Atenção'),
                'CAUTION': ('calloutKbCaution', 'bi-shield-fill-x', 'Cuidado')
            }
            classe_css, icone, titulo_default = classes.get(tipo, ('calloutKbNote', 'bi-info-circle-fill', tipo))

            return f'''<div class="calloutKb {classe_css}">
                <div class="calloutKbHeader">
                    <i class="bi {icone} me-1"></i> {titulo_default}
                </div>
                <div class="calloutKbBody">{corpo}</div>
            </div>\n'''

        return re.sub(padrao, substituir_callout, texto, flags=re.MULTILINE)

    @classmethod
    def listar_artigos(cls, busca='', categoria_slug='', tag_slug='', ordem='relevancia', status='publicado'):
        """Retorna lista de artigos filtrados e ordenados."""
        query = KbArtigo.query

        if status:
            query = query.filter(KbArtigo.status == status)

        if categoria_slug:
            query = query.join(KbCategoria).filter(KbCategoria.slug == categoria_slug)

        if tag_slug:
            query = query.join(KbArtigo.tags).filter(KbTag.slug == tag_slug)

        if busca:
            termo = f"%{busca}%"
            query = query.filter(
                db.or_(
                    KbArtigo.titulo.ilike(termo),
                    KbArtigo.resumo.ilike(termo),
                    KbArtigo.conteudo_md.ilike(termo)
                )
            )

        artigos = query.all()

        # Ordenação
        if ordem == 'uteis':
            artigos.sort(key=lambda a: (a.percentual_util, a.votos_util), reverse=True)
        elif ordem == 'acessados':
            artigos.sort(key=lambda a: (a.visualizacoes or 0), reverse=True)
        elif ordem == 'recentes':
            artigos.sort(key=lambda a: a.data_atualizacao or a.data_criacao, reverse=True)
        else: # 'relevancia'
            artigos.sort(key=lambda a: a.score_relevancia, reverse=True)

        return artigos

    @classmethod
    def obter_artigo_por_slug(cls, slug, incrementar_views=True):
        """Busca artigo pelo slug e opcionalmente incrementa visualizações."""
        artigo = KbArtigo.query.filter_by(slug=slug).first()
        if artigo and incrementar_views:
            artigo.visualizacoes = (artigo.visualizacoes or 0) + 1
            db.session.commit()
        return artigo

    @classmethod
    def registrar_feedback(cls, artigo_id, util, usuario_id=None, comentario=None):
        """Registra voto útil (👍) ou não útil (👎) com comentário opcional."""
        artigo = db.session.get(KbArtigo, artigo_id)
        if not artigo:
            return False, "Artigo não encontrado."

        feedback = KbFeedback(
            artigo_id=artigo_id,
            usuario_id=usuario_id,
            util=bool(util),
            comentario=comentario.strip() if comentario else None
        )
        db.session.add(feedback)

        if util:
            artigo.votos_util = (artigo.votos_util or 0) + 1
        else:
            artigo.votos_inutil = (artigo.votos_inutil or 0) + 1

        db.session.commit()
        return True, "Obrigado pelo seu feedback! Ele nos ajuda a aprimorar nossos procedimentos."

    @classmethod
    def criar_solicitacao(cls, titulo, descricao, categoria_id, justificativa, prioridade, usuario_id):
        """Registra pedido de criação ou atualização de artigo por usuário comum."""
        solicitacao = KbSolicitacao(
            titulo=titulo.strip(),
            descricao=descricao.strip(),
            categoria_id=categoria_id if categoria_id else None,
            justificativa=justificativa.strip() if justificativa else None,
            prioridade=prioridade or 'normal',
            solicitante_id=usuario_id,
            status='pendente'
        )
        db.session.add(solicitacao)
        db.session.commit()
        return solicitacao

    @classmethod
    def obter_kpis_admin(cls):
        """Calcula métricas analíticas da base de conhecimento."""
        total_artigos = KbArtigo.query.count()
        artigos_publicados = KbArtigo.query.filter_by(status='publicado').count()
        artigos_rascunho = KbArtigo.query.filter_by(status='rascunho').count()
        solicitacoes_pendentes = KbSolicitacao.query.filter_by(status='pendente').count()

        mais_acessados = KbArtigo.query.order_by(KbArtigo.visualizacoes.desc()).limit(5).all()
        menos_acessados = KbArtigo.query.filter_by(status='publicado').order_by(KbArtigo.visualizacoes.asc()).limit(5).all()
        
        # Artigos que precisam de revisão (mais de 2 votos negativos ou taxa < 75%)
        precisam_revisao = [
            a for a in KbArtigo.query.filter_by(status='publicado').all()
            if a.total_votos >= 3 and a.percentual_util < 80
        ]

        total_votos = db.session.query(db.func.count(KbFeedback.id)).scalar() or 0
        votos_positivos = db.session.query(db.func.count(KbFeedback.id)).filter(KbFeedback.util == True).scalar() or 0
        taxa_satisfacao = int(round((votos_positivos / total_votos) * 100)) if total_votos > 0 else 100
        total_visualizacoes = db.session.query(db.func.sum(KbArtigo.visualizacoes)).scalar() or 0

        return {
            'total_artigos': total_artigos,
            'artigos_publicados': artigos_publicados,
            'artigos_rascunho': artigos_rascunho,
            'total_visualizacoes': total_visualizacoes,
            'total_feedbacks': total_votos,
            'taxa_aprovacao': taxa_satisfacao,
            'taxa_satisfacao': taxa_satisfacao,
            'solicitacoes_pendentes': solicitacoes_pendentes,
            'mais_acessados': mais_acessados,
            'menos_acessados': menos_acessados,
            'precisam_revisao': precisam_revisao
        }

    @classmethod
    def seed_dados_iniciais(cls):
        """Cria categorias e artigos iniciais se o banco estiver vazio."""
        if KbCategoria.query.first():
            return

        categorias = [
            KbCategoria(nome="Impressoras & Suprimentos", slug="impressoras-suprimentos", icone="bi-printer-fill", descricao="Configuração de IP, drivers, troca de toners e cilindros.", ordem=1),
            KbCategoria(nome="Redes & Infraestrutura", slug="redes-infraestrutura", icone="bi-hdd-network-fill", descricao="Mapeamentos de rede, switches, Wi-Fi e VPN corporativa.", ordem=2),
            KbCategoria(nome="Estações de Trabalho", slug="estacoes-trabalho", icone="bi-pc-display", descricao="Sistema operacional Windows, softwares padrões e formatação.", ordem=3),
            KbCategoria(nome="Sistemas & Acessos", slug="sistemas-acessos", icone="bi-shield-lock-fill", descricao="Contas do Active Directory, permissões e e-mail corporativo.", ordem=4),
            KbCategoria(nome="Procedimentos & POPs", slug="procedimentos-pops", icone="bi-card-checklist", descricao="Procedimentos Operacionais Padrão e boas práticas de TI.", ordem=5),
        ]
        db.session.add_all(categorias)
        db.session.commit()

        # Busca autor administrador
        admin = Usuario.query.filter_by(perfil='admin').first() or Usuario.query.first()
        if not admin:
            return

        cat_imp = KbCategoria.query.filter_by(slug="impressoras-suprimentos").first()
        cat_rede = KbCategoria.query.filter_by(slug="redes-infraestrutura").first()
        cat_pop = KbCategoria.query.filter_by(slug="procedimentos-pops").first()

        # Tags
        tag_brother = KbTag(nome="brother", slug="brother")
        tag_ip = KbTag(nome="ip", slug="ip")
        tag_vpn = KbTag(nome="vpn", slug="vpn")
        tag_chamado = KbTag(nome="chamados", slug="chamados")
        db.session.add_all([tag_brother, tag_ip, tag_vpn, tag_chamado])
        db.session.commit()

        # Artigo 1: Impressora Brother
        art1 = KbArtigo(
            titulo="Como Configurar Endereço IP Fixo na Linha Brother DCP-8112 / 8157",
            slug="como-configurar-ip-fixo-brother-dcp-8112",
            resumo="Guia passo a passo para atribuição de IP estático, máscara de rede e gateway no painel físico das impressoras multifuncionais Brother.",
            conteudo_md="""# Como Configurar Endereço IP Fixo na Linha Brother

Este procedimento documenta o método oficial para fixar o endereço IP nos equipamentos multifuncionais Brother alocados em contratos e setores internos.

> [!NOTE]
> Equipamentos em contratos externos não utilizam DHCP automático. O endereço IP deve ser sempre configurado no modo estático.

## 1. Requisitos Prévios

Antes de realizar a configuração no painel, verifique:
- O endereço IP reservado no cadastro de ativos da rede.
- A máscara de sub-rede padrão (`255.255.0.0` ou `255.255.255.0`).
- O gateway correspondente ao roteador/switch local.

## 2. Acesso ao Painel Físico

1. No teclado numérico da impressora, pressione a tecla **Menu**.
2. Navegue utilizando as setas para baixo até a opção **7. Rede** e pressione **OK**.
3. Selecione a opção **1. TCP/IP** e pressione **OK**.
4. Em **Método BOOT**, altere de `Auto` para **Estático** e pressione **OK**.

## 3. Inserção dos Parâmetros de Rede

- **Endereço IP:** Insira o IP atribuído utilizando o teclado numérico (ex: `10.90.1.25`).
- **Máscara de Sub-rede:** Pressione **OK** e defina `255.255.0.0`.
- **Gateway Padrão:** Insira o IP do gateway local.

## 4. Teste de Conexão no Prompt de Comando

Após reiniciar o equipamento, abra o PowerShell no seu computador e execute:

```powershell
ping 10.90.1.25 -n 4
```

> [!TIP]
> Se o ping responder em menos de 5ms, o equipamento está pronto para ser adicionado ao monitoramento da Central de Chamados!
""",
            categoria_id=cat_imp.id,
            autor_id=admin.id,
            status='publicado',
            tempo_leitura_min=3,
            visualizacoes=145,
            votos_util=24,
            votos_inutil=1
        )
        db.session.add(art1)
        art1.tags.extend([tag_brother, tag_ip])

        # Artigo 2: Conexão VPN
        art2 = KbArtigo(
            titulo="Instalação e Conexão da VPN Corporativa no Windows 11",
            slug="instalacao-conexao-vpn-corporativa-windows-11",
            resumo="Instruções completas para download do certificado, importação de perfil e autenticação em 2 fatores para acesso remoto à rede da empresa.",
            conteudo_md="""# Conexão VPN Corporativa no Windows 11

Tutorial para colaboradores em regime híbrido ou técnicos externos acessarem com segurança os servidores e sistemas locais.

> [!IMPORTANT]
> O acesso à VPN requer aprovação prévia da diretoria e conta habilitada no Active Directory.

## 1. Baixar o Cliente Oficial

1. Baixe o instalador oficial do cliente VPN homologado pelo departamento de TI.
2. Execute o instalador como **Administrador**.

## 2. Configurar o Host do Servidor

- **Endereço do Servidor:** `vpn.empresa.com.br`
- **Porta:** `1194` (Protocolo UDP)
- **Tipo de Túnel:** Split-Tunnel (apenas tráfego da rede interna é criptografado).

## 3. Teste de Acesso aos Serviços Locais

Com a VPN conectada, abra o navegador e acesse a Central de Chamados pelo endereço da rede local:

```text
http://172.16.50.5:5000
```

> [!WARNING]
> Nunca compartilhe suas credenciais ou arquivos `.ovpn` com terceiros.
""",
            categoria_id=cat_rede.id,
            autor_id=admin.id,
            status='publicado',
            tempo_leitura_min=4,
            visualizacoes=289,
            votos_util=52,
            votos_inutil=2
        )
        db.session.add(art2)
        art2.tags.extend([tag_vpn])

        db.session.commit()
