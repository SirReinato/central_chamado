import io
import logging
import calendar
from datetime import datetime, timedelta
from sqlalchemy import func, or_, desc
from models import db, ItemSala, ItemSalaEstoque, ItemSalaMovimentacao, Usuario

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

logger = logging.getLogger('central_chamados')


class ItensSalaNumberedCanvas(canvas.Canvas):
    """Canvas customizado do ReportLab para numeração dinâmica de páginas (Página X de Y) em Landscape."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        # Rodapé em página paisagem (A4 Landscape: largura 841.89 pt, margens 30 pt)
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(841.89 - 30, 16, page_text)
        self.drawString(30, 16, "Hub Central - SirReinato Brasfort — Almoxarifado TI: Relatório de Itens por Sala e Saídas Mensais")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(30, 26, 841.89 - 30, 26)
        self.restoreState()


class ItensSalaService:
    SALA_PRINCIPAL = 'Sala Principal'
    SALA_3_ANDAR = 'Sala TI - 3º Andar'
    SALAS_VALIDAS = [SALA_PRINCIPAL, SALA_3_ANDAR]

    CATEGORIAS_PADRAO = [
        'Periféricos',
        'Hardware',
        'Monitores',
        'Cabos & Conectores',
        'Fontes & Energia',
        'Rede & Telefonia',
        'Acessórios & Outros'
    ]

    ORIGENS_ENTRADA = [
        'Compra Nova',
        'Fornecedor / Garantia',
        'Devolução de Usuário',
        'Remanejamento Externo',
        'Doação / Sucata Recuperada',
        'Outro'
    ]

    # Mapeamento de ícones por categoria ou nome
    @staticmethod
    def obter_icone_item(nome, categoria):
        nome_lower = (nome or '').lower()
        if 'teclado' in nome_lower:
            return 'bi-keyboard'
        if 'mouse' in nome_lower:
            return 'bi-mouse'
        if 'headset' in nome_lower or 'fone' in nome_lower:
            return 'bi-headset'
        if 'monitor' in nome_lower or 'tela' in nome_lower:
            return 'bi-display'
        if 'cabo' in nome_lower or 'patch' in nome_lower:
            return 'bi-ethernet'
        if 'hd' in nome_lower or 'ssd' in nome_lower or 'disco' in nome_lower:
            return 'bi-device-hdd'
        if 'memória' in nome_lower or 'ram' in nome_lower:
            return 'bi-memory'
        if 'fonte' in nome_lower:
            return 'bi-lightning-charge'
        if 'adaptador' in nome_lower or 'conversor' in nome_lower:
            return 'bi-plug'
        if 'placa' in nome_lower:
            return 'bi-motherboard'

        # Fallback por categoria
        cat_map = {
            'Periféricos': 'bi-mouse',
            'Hardware': 'bi-cpu',
            'Monitores': 'bi-display',
            'Cabos & Conectores': 'bi-ethernet',
            'Fontes & Energia': 'bi-lightning-charge',
            'Rede & Telefonia': 'bi-router',
            'Acessórios & Outros': 'bi-box-seam'
        }
        return cat_map.get(categoria, 'bi-box-seam')

    @classmethod
    def seed_inicial(cls):
        """Catálogo inicial limpo/vazio para cadastro manual sob demanda."""
        pass

    @classmethod
    def obter_kpis(cls):
        """Retorna indicadores chave de desempenho para os cards superiores."""
        hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        mes_inicio = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Total de itens físicos disponíveis
        total_itens = db.session.query(func.coalesce(func.sum(ItemSalaEstoque.quantidade), 0))\
            .join(ItemSala, ItemSala.id == ItemSalaEstoque.item_id)\
            .filter(ItemSala.ativo == True).scalar() or 0

        # Materiais diferentes cadastrados
        materiais_diferentes = ItemSala.query.filter_by(ativo=True).count()

        # Itens retirados hoje
        retirados_hoje = db.session.query(func.coalesce(func.sum(ItemSalaMovimentacao.quantidade), 0))\
            .filter(
                ItemSalaMovimentacao.tipo == 'saida',
                ItemSalaMovimentacao.created_at >= hoje_inicio
            ).scalar() or 0

        # Total de movimentações no mês
        movimentacoes_mes = ItemSalaMovimentacao.query.filter(
            ItemSalaMovimentacao.created_at >= mes_inicio
        ).count()

        # Itens com estoque baixo
        itens_ativos = ItemSala.query.filter_by(ativo=True).all()
        itens_baixo_estoque = [it for it in itens_ativos if it.is_estoque_baixo]

        return {
            'total_itens': total_itens,
            'materiais_diferentes': materiais_diferentes,
            'retirados_hoje': retirados_hoje,
            'movimentacoes_mes': movimentacoes_mes,
            'qtd_baixo_estoque': len(itens_baixo_estoque),
            'itens_baixo_estoque': itens_baixo_estoque
        }

    @classmethod
    def obter_resumo_por_sala(cls, busca=None, categoria=None):
        """
        Retorna os dados agrupados para visualização lado a lado das salas.
        Cada sala possui total de unidades e lista de itens com estoque.
        """
        itens_query = ItemSala.query.filter_by(ativo=True)

        if categoria and categoria != 'todas':
            itens_query = itens_query.filter(ItemSala.categoria == categoria)

        if busca:
            termo = f"%{busca.strip()}%"
            itens_query = itens_query.filter(
                or_(
                    ItemSala.nome.ilike(termo),
                    ItemSala.categoria.ilike(termo),
                    ItemSala.descricao.ilike(termo)
                )
            )

        itens = itens_query.order_by(ItemSala.nome.asc()).all()

        sala_principal_itens = []
        sala_terceiro_itens = []
        total_sp = 0
        total_st = 0

        for it in itens:
            qtd_sp = it.estoque_sala_principal
            qtd_st = it.estoque_sala_terceiro
            total_sp += qtd_sp
            total_st += qtd_st

            icone = cls.obter_icone_item(it.nome, it.categoria)

            # Item formatado para Sala Principal
            sala_principal_itens.append({
                'id': it.id,
                'nome': it.nome,
                'categoria': it.categoria,
                'estoque_minimo': it.estoque_minimo,
                'unidade': it.unidade,
                'quantidade': qtd_sp,
                'total_geral': it.total_estoque,
                'is_baixo': qtd_sp <= 1 or it.is_estoque_baixo,
                'icone': icone
            })

            # Item formatado para Sala 3º Andar
            sala_terceiro_itens.append({
                'id': it.id,
                'nome': it.nome,
                'categoria': it.categoria,
                'estoque_minimo': it.estoque_minimo,
                'unidade': it.unidade,
                'quantidade': qtd_st,
                'total_geral': it.total_estoque,
                'is_baixo': qtd_st <= 1 or it.is_estoque_baixo,
                'icone': icone
            })

        return {
            'sala_principal': {
                'nome': cls.SALA_PRINCIPAL,
                'icone': 'bi-pc-display',
                'descricao': 'Sala Central de Suporte & Manutenção TI',
                'total_unidades': total_sp,
                'total_tipos': sum(1 for it in sala_principal_itens if it['quantidade'] > 0),
                'itens': sala_principal_itens
            },
            'sala_3_andar': {
                'nome': cls.SALA_3_ANDAR,
                'icone': 'bi-building-fill-gear',
                'descricao': 'Ponto de Apoio Operacional TI - 3º Pavimento',
                'total_unidades': total_st,
                'total_tipos': sum(1 for it in sala_terceiro_itens if it['quantidade'] > 0),
                'itens': sala_terceiro_itens
            }
        }

    @classmethod
    def listar_todos_itens(cls):
        """Retorna lista simplificada para selects de formulários."""
        return ItemSala.query.filter_by(ativo=True).order_by(ItemSala.nome.asc()).all()

    @classmethod
    def criar_item(cls, nome, categoria, estoque_minimo, sala_inicial, qtd_inicial, descricao=None, unidade='UN', usuario_id=None):
        """Cadastra um novo material e inicializa seus estoques nas salas."""
        nome = (nome or '').strip()
        if not nome:
            raise ValueError("O nome do item é obrigatório.")

        categoria = (categoria or 'Periféricos').strip()
        estoque_minimo = max(0, int(estoque_minimo or 0))
        qtd_inicial = max(0, int(qtd_inicial or 0))

        if sala_inicial not in cls.SALAS_VALIDAS:
            sala_inicial = cls.SALA_PRINCIPAL

        item_existente = ItemSala.query.filter(func.lower(ItemSala.nome) == nome.lower(), ItemSala.ativo == True).first()
        if item_existente:
            raise ValueError(f"Já existe um item ativo cadastrado com o nome '{nome}'.")

        item = ItemSala(
            nome=nome,
            categoria=categoria,
            estoque_minimo=estoque_minimo,
            unidade=unidade or 'UN',
            descricao=descricao.strip() if descricao else None,
            ativo=True
        )
        db.session.add(item)
        db.session.flush()

        # Cria os dois estoques
        qtd_sp = qtd_inicial if sala_inicial == cls.SALA_PRINCIPAL else 0
        qtd_st = qtd_inicial if sala_inicial == cls.SALA_3_ANDAR else 0

        est_sp = ItemSalaEstoque(item_id=item.id, sala=cls.SALA_PRINCIPAL, quantidade=qtd_sp)
        est_st = ItemSalaEstoque(item_id=item.id, sala=cls.SALA_3_ANDAR, quantidade=qtd_st)
        db.session.add(est_sp)
        db.session.add(est_st)

        if qtd_inicial > 0:
            mov = ItemSalaMovimentacao(
                item_id=item.id,
                tipo='entrada',
                quantidade=qtd_inicial,
                sala_destino=sala_inicial,
                entregue_por='Cadastro Inicial',
                recebido_por='Equipe TI',
                setor='TI / Estoque',
                origem_fornecedor='Estoque Inicial',
                observacao=f"Entrada inicial de cadastro na {sala_inicial}",
                usuario_id=usuario_id
            )
            db.session.add(mov)

        db.session.commit()
        return item

    @classmethod
    def editar_item(cls, item_id, nome, categoria, estoque_minimo, descricao=None, unidade='UN'):
        """Atualiza informações cadastrais de um material."""
        item = ItemSala.query.get(item_id)
        if not item or not item.ativo:
            raise ValueError("Item não encontrado.")

        nome = (nome or '').strip()
        if not nome:
            raise ValueError("O nome do item não pode ser vazio.")

        item.nome = nome
        item.categoria = categoria or item.categoria
        item.estoque_minimo = max(0, int(estoque_minimo or 0))
        item.descricao = descricao.strip() if descricao else None
        item.unidade = unidade or 'UN'

        db.session.commit()
        return item

    @classmethod
    def excluir_item(cls, item_id):
        """Desativa o item (soft-delete preservando integridade das movimentações)."""
        item = ItemSala.query.get(item_id)
        if not item:
            raise ValueError("Item não encontrado.")
        item.ativo = False
        db.session.commit()
        return True

    @classmethod
    def registrar_saida(cls, item_id, sala, quantidade, entregue_por, recebido_por, setor, observacao=None, usuario_id=None):
        """Registra a saída/retirada de um item da sala especificada."""
        item = ItemSala.query.get(item_id)
        if not item or not item.ativo:
            raise ValueError("Item inválido ou inativo.")

        if sala not in cls.SALAS_VALIDAS:
            raise ValueError(f"Sala de origem inválida. Escolha entre: {', '.join(cls.SALAS_VALIDAS)}")

        quantidade = int(quantidade or 0)
        if quantidade <= 0:
            raise ValueError("A quantidade retirada deve ser maior que zero.")

        entregue_por = (entregue_por or '').strip()
        recebido_por = (recebido_por or '').strip()
        setor = (setor or '').strip()

        if not recebido_por:
            raise ValueError("Informe o nome de quem retirou o item.")
        if not setor:
            raise ValueError("Informe o setor de destino do item.")

        # Localiza o registro de estoque da sala
        estoque_sala = ItemSalaEstoque.query.filter_by(item_id=item.id, sala=sala).first()
        if not estoque_sala or estoque_sala.quantidade < quantidade:
            saldo_atual = estoque_sala.quantidade if estoque_sala else 0
            raise ValueError(
                f"Saldo insuficiente na {sala}. Disponível: {saldo_atual} {item.unidade}, solicitado: {quantidade} {item.unidade}."
            )

        # Deduz estoque
        estoque_sala.quantidade -= quantidade

        # Cria movimentação
        mov = ItemSalaMovimentacao(
            item_id=item.id,
            tipo='saida',
            quantidade=quantidade,
            sala_origem=sala,
            entregue_por=entregue_por or 'Técnico TI',
            recebido_por=recebido_por,
            setor=setor,
            observacao=observacao.strip() if observacao else None,
            usuario_id=usuario_id
        )
        db.session.add(mov)
        db.session.commit()
        return mov

    @classmethod
    def registrar_entrada(cls, item_id, sala, quantidade, adicionado_por, origem=None, observacao=None, usuario_id=None):
        """Registra entrada/reposição de material em uma sala."""
        item = ItemSala.query.get(item_id)
        if not item or not item.ativo:
            raise ValueError("Item inválido ou inativo.")

        if sala not in cls.SALAS_VALIDAS:
            raise ValueError(f"Sala de destino inválida. Escolha entre: {', '.join(cls.SALAS_VALIDAS)}")

        quantidade = int(quantidade or 0)
        if quantidade <= 0:
            raise ValueError("A quantidade de entrada deve ser maior que zero.")

        adicionado_por = (adicionado_por or '').strip()

        estoque_sala = ItemSalaEstoque.query.filter_by(item_id=item.id, sala=sala).first()
        if not estoque_sala:
            estoque_sala = ItemSalaEstoque(item_id=item.id, sala=sala, quantidade=0)
            db.session.add(estoque_sala)

        estoque_sala.quantidade += quantidade

        mov = ItemSalaMovimentacao(
            item_id=item.id,
            tipo='entrada',
            quantidade=quantidade,
            sala_destino=sala,
            entregue_por=origem or 'Entrada',
            recebido_por=adicionado_por or 'Técnico TI',
            origem_fornecedor=origem or 'Reposição',
            setor='TI / Almoxarifado',
            observacao=observacao.strip() if observacao else None,
            usuario_id=usuario_id
        )
        db.session.add(mov)
        db.session.commit()
        return mov

    @classmethod
    def transferir_entre_salas(cls, item_id, sala_origem, sala_destino, quantidade, responsavel, motivo=None, usuario_id=None):
        """Transfere uma quantidade de itens de uma sala para a outra."""
        item = ItemSala.query.get(item_id)
        if not item or not item.ativo:
            raise ValueError("Item inválido ou inativo.")

        if sala_origem not in cls.SALAS_VALIDAS or sala_destino not in cls.SALAS_VALIDAS:
            raise ValueError("Salas de origem e destino devem ser válidas.")

        if sala_origem == sala_destino:
            raise ValueError("A sala de origem não pode ser igual à sala de destino.")

        quantidade = int(quantidade or 0)
        if quantidade <= 0:
            raise ValueError("A quantidade a transferir deve ser maior que zero.")

        responsavel = (responsavel or '').strip()
        if not responsavel:
            raise ValueError("Informe o responsável pela transferência.")

        est_origem = ItemSalaEstoque.query.filter_by(item_id=item.id, sala=sala_origem).first()
        if not est_origem or est_origem.quantidade < quantidade:
            saldo_atual = est_origem.quantidade if est_origem else 0
            raise ValueError(
                f"Saldo insuficiente na {sala_origem}. Disponível: {saldo_atual} {item.unidade}, solicitada transferência de: {quantidade} {item.unidade}."
            )

        est_destino = ItemSalaEstoque.query.filter_by(item_id=item.id, sala=sala_destino).first()
        if not est_destino:
            est_destino = ItemSalaEstoque(item_id=item.id, sala=sala_destino, quantidade=0)
            db.session.add(est_destino)

        # Atualiza saldos
        est_origem.quantidade -= quantidade
        est_destino.quantidade += quantidade

        # Registra movimentação de transferência
        mov = ItemSalaMovimentacao(
            item_id=item.id,
            tipo='transferencia',
            quantidade=quantidade,
            sala_origem=sala_origem,
            sala_destino=sala_destino,
            entregue_por=responsavel,
            recebido_por=responsavel,
            setor='Transferência Interna TI',
            observacao=motivo.strip() if motivo else 'Transferência entre salas operacionais',
            usuario_id=usuario_id
        )
        db.session.add(mov)
        db.session.commit()
        return mov

    @classmethod
    def obter_historico(cls, tipo=None, sala=None, setor=None, busca=None, data_inicio=None, data_fim=None, limite=150):
        """Retorna histórico filtrado com paginação/limite para timeline e auditoria."""
        query = ItemSalaMovimentacao.query.join(ItemSala, ItemSala.id == ItemSalaMovimentacao.item_id)

        if tipo and tipo != 'todos':
            query = query.filter(ItemSalaMovimentacao.tipo == tipo)

        if sala and sala != 'todas':
            query = query.filter(
                or_(
                    ItemSalaMovimentacao.sala_origem == sala,
                    ItemSalaMovimentacao.sala_destino == sala
                )
            )

        if setor:
            query = query.filter(ItemSalaMovimentacao.setor.ilike(f"%{setor.strip()}%"))

        if busca:
            termo = f"%{busca.strip()}%"
            query = query.filter(
                or_(
                    ItemSala.nome.ilike(termo),
                    ItemSalaMovimentacao.recebido_por.ilike(termo),
                    ItemSalaMovimentacao.entregue_por.ilike(termo),
                    ItemSalaMovimentacao.setor.ilike(termo),
                    ItemSalaMovimentacao.observacao.ilike(termo)
                )
            )

        if data_inicio:
            try:
                dt_ini = datetime.strptime(data_inicio, '%Y-%m-%d')
                query = query.filter(ItemSalaMovimentacao.created_at >= dt_ini)
            except Exception:
                pass

        if data_fim:
            try:
                dt_fim = datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                query = query.filter(ItemSalaMovimentacao.created_at <= dt_fim)
            except Exception:
                pass

        return query.order_by(desc(ItemSalaMovimentacao.created_at)).limit(limite).all()

    @classmethod
    def obter_dados_graficos(cls):
        """Retorna dados agregados para renderização dos gráficos (Chart.js)."""
        trinta_dias_atras = datetime.now() - timedelta(days=30)

        # 1. Top 7 Itens mais retirados
        top_itens_raw = db.session.query(
            ItemSala.nome,
            func.sum(ItemSalaMovimentacao.quantidade).label('total_retirado')
        ).join(ItemSala, ItemSala.id == ItemSalaMovimentacao.item_id)\
         .filter(ItemSalaMovimentacao.tipo == 'saida')\
         .group_by(ItemSala.nome)\
         .order_by(desc('total_retirado'))\
         .limit(7).all()

        top_itens_labels = [r[0] for r in top_itens_raw]
        top_itens_data = [int(r[1]) for r in top_itens_raw]

        # 2. Retiradas por Setor (Top 6)
        setores_raw = db.session.query(
            ItemSalaMovimentacao.setor,
            func.sum(ItemSalaMovimentacao.quantidade).label('total_setor')
        ).filter(
            ItemSalaMovimentacao.tipo == 'saida',
            ItemSalaMovimentacao.setor != None,
            ItemSalaMovimentacao.setor != ''
        ).group_by(ItemSalaMovimentacao.setor)\
         .order_by(desc('total_setor'))\
         .limit(6).all()

        setores_labels = [r[0] for r in setores_raw]
        setores_data = [int(r[1]) for r in setores_raw]

        # 3. Distribuição de Estoque por Sala
        total_sp = db.session.query(func.coalesce(func.sum(ItemSalaEstoque.quantidade), 0))\
            .join(ItemSala, ItemSala.id == ItemSalaEstoque.item_id)\
            .filter(ItemSala.ativo == True, ItemSalaEstoque.sala == cls.SALA_PRINCIPAL).scalar() or 0

        total_st = db.session.query(func.coalesce(func.sum(ItemSalaEstoque.quantidade), 0))\
            .join(ItemSala, ItemSala.id == ItemSalaEstoque.item_id)\
            .filter(ItemSala.ativo == True, ItemSalaEstoque.sala == cls.SALA_3_ANDAR).scalar() or 0

        # 4. Movimentações nos últimos 14 dias (Entradas vs Saídas)
        catorze_dias = []
        dias_labels = []
        entradas_serie = []
        saidas_serie = []

        hoje = datetime.now().date()
        for i in range(13, -1, -1):
            dia = hoje - timedelta(days=i)
            dias_labels.append(dia.strftime('%d/%m'))
            inicio = datetime.combine(dia, datetime.min.time())
            fim = datetime.combine(dia, datetime.max.time())

            qtd_ent = db.session.query(func.coalesce(func.sum(ItemSalaMovimentacao.quantidade), 0))\
                .filter(
                    ItemSalaMovimentacao.tipo == 'entrada',
                    ItemSalaMovimentacao.created_at >= inicio,
                    ItemSalaMovimentacao.created_at <= fim
                ).scalar() or 0

            qtd_sai = db.session.query(func.coalesce(func.sum(ItemSalaMovimentacao.quantidade), 0))\
                .filter(
                    ItemSalaMovimentacao.tipo == 'saida',
                    ItemSalaMovimentacao.created_at >= inicio,
                    ItemSalaMovimentacao.created_at <= fim
                ).scalar() or 0

            entradas_serie.append(int(qtd_ent))
            saidas_serie.append(int(qtd_sai))

        return {
            'top_itens': {
                'labels': top_itens_labels or ['Nenhum registro'],
                'data': top_itens_data or [0]
            },
            'setores': {
                'labels': setores_labels or ['Sem registros'],
                'data': setores_data or [0]
            },
            'salas_proporcao': {
                'labels': [cls.SALA_PRINCIPAL, cls.SALA_3_ANDAR],
                'data': [int(total_sp), int(total_st)]
            },
            'fluxo_dias': {
                'labels': dias_labels,
                'entradas': entradas_serie,
                'saidas': saidas_serie
            }
        }

    @classmethod
    def gerar_relatorio_pdf(cls, mes=None, ano=None, emitido_por=None):
        """
        Gera relatório executivo em PDF (Landscape A4) contendo:
        1. Indicadores consolidados do almoxarifado.
        2. Tabela de posição atual de estoque em cada sala (Sala Principal e Sala TI - 3º Andar).
        3. Histórico detalhado de saídas/retiradas de materiais no mês vigente (ou mês informado).
        4. Resumo analítico de saídas por setor solicitante e por material.
        """
        MESES_PT = [
            '', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
        ]
        agora = datetime.now()
        if not ano:
            ano = agora.year
        if not mes:
            mes = agora.month

        nome_mes = MESES_PT[mes] if 1 <= mes <= 12 else str(mes)
        periodo_str = f"{nome_mes} de {ano}"
        agora_str = agora.strftime("%d/%m/%Y %H:%M")
        responsavel_str = emitido_por or "Equipe de TI"

        inicio_mes = datetime(ano, mes, 1, 0, 0, 0)
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        fim_mes = datetime(ano, mes, ultimo_dia, 23, 59, 59)

        # 1. Carrega dados de estoque atual
        itens = ItemSala.query.filter_by(ativo=True).order_by(ItemSala.categoria.asc(), ItemSala.nome.asc()).all()

        total_itens_sp = 0
        total_itens_st = 0
        itens_com_baixo_estoque = 0
        dados_itens_estoque = []

        for item in itens:
            sp = item.estoque_sala_principal
            st = item.estoque_sala_terceiro
            tot = sp + st
            total_itens_sp += sp
            total_itens_st += st
            baixo = tot <= (item.estoque_minimo or 0)
            if baixo:
                itens_com_baixo_estoque += 1

            dados_itens_estoque.append({
                'id': item.id,
                'nome': item.nome,
                'categoria': item.categoria,
                'unidade': item.unidade or 'UN',
                'estoque_minimo': item.estoque_minimo or 0,
                'sp': sp,
                'st': st,
                'total': tot,
                'baixo': baixo
            })

        # 2. Carrega saídas do mês vigente
        saidas = ItemSalaMovimentacao.query.join(
            ItemSala, ItemSala.id == ItemSalaMovimentacao.item_id
        ).filter(
            ItemSalaMovimentacao.tipo == 'saida',
            ItemSalaMovimentacao.created_at >= inicio_mes,
            ItemSalaMovimentacao.created_at <= fim_mes
        ).order_by(
            ItemSalaMovimentacao.created_at.asc()
        ).all()

        total_saidas_qtd = sum(s.quantidade for s in saidas)
        total_saidas_registros = len(saidas)

        # 3. Agrupamento de saídas por setor e material
        setores_agrupados = {}
        materiais_agrupados = {}
        for s in saidas:
            setor_nome = (s.setor or 'Não Informado').strip()
            setores_agrupados[setor_nome] = setores_agrupados.get(setor_nome, 0) + s.quantidade

            mat_nome = s.item.nome if s.item else f"Item #{s.item_id}"
            materiais_agrupados[mat_nome] = materiais_agrupados.get(mat_nome, 0) + s.quantidade

        setores_ranking = sorted(setores_agrupados.items(), key=lambda x: x[1], reverse=True)
        materiais_ranking = sorted(materiais_agrupados.items(), key=lambda x: x[1], reverse=True)

        # Configuração do documento ReportLab
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            leftMargin=30,
            rightMargin=30,
            topMargin=26,
            bottomMargin=32
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=17,
            textColor=colors.HexColor('#0f172a'),
            spaceAfter=2
        )

        subtitle_style = ParagraphStyle(
            'ReportSubTitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=8
        )

        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=10.5,
            leading=13,
            textColor=colors.HexColor('#0f172a'),
            spaceBefore=6,
            spaceAfter=4
        )

        th_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#ffffff')
        )

        th_center = ParagraphStyle(
            'TableHeaderCenter',
            parent=th_style,
            alignment=1
        )

        td_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#1e293b')
        )

        td_center = ParagraphStyle(
            'TableCellCenter',
            parent=td_style,
            alignment=1
        )

        td_bold = ParagraphStyle(
            'TableCellBold',
            parent=td_style,
            fontName='Helvetica-Bold'
        )

        td_bold_center = ParagraphStyle(
            'TableCellBoldCenter',
            parent=td_style,
            fontName='Helvetica-Bold',
            alignment=1
        )

        td_warning = ParagraphStyle(
            'TableCellWarning',
            parent=td_style,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#b45309'),
            alignment=1
        )

        td_success = ParagraphStyle(
            'TableCellSuccess',
            parent=td_style,
            textColor=colors.HexColor('#15803d'),
            alignment=1
        )

        kpi_label = ParagraphStyle(
            'KpiLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor('#475569'),
            alignment=1
        )

        kpi_val = ParagraphStyle(
            'KpiVal',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=14,
            textColor=colors.HexColor('#0f172a'),
            alignment=1
        )

        kpi_sub = ParagraphStyle(
            'KpiSub',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=6.5,
            leading=8,
            textColor=colors.HexColor('#64748b'),
            alignment=1
        )

        def criar_estilo_tabela_zebrada(num_linhas, header_bg='#0f172a'):
            t_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_bg)),
                ('TOPPADDING', (0, 0), (-1, 0), 4),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ])
            for i in range(1, num_linhas):
                if i % 2 == 0:
                    t_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8fafc'))
                else:
                    t_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#ffffff'))
            return t_style

        elements = []

        # ==================================================================
        # CABEÇALHO DO RELATÓRIO
        # ==================================================================
        elements.append(Paragraph(
            "RELATÓRIO DE ITENS POR SALA E SAÍDAS DO MÊS VIGENTE",
            title_style
        ))
        elements.append(Paragraph(
            f"Hub Central - SirReinato Brasfort — Almoxarifado TI | Mês de Referência: <b>{periodo_str}</b> | Emitido em: <b>{agora_str}</b> | Responsável: <b>{responsavel_str}</b>",
            subtitle_style
        ))

        # ==================================================================
        # CARDS DE KPIS / RESUMO
        # ==================================================================
        kpi_cells = [
            [
                Paragraph("SALA PRINCIPAL", kpi_label),
                Paragraph("SALA TI - 3º ANDAR", kpi_label),
                Paragraph("ESTOQUE CONSOLIDADO", kpi_label),
                Paragraph(f"SAÍDAS ({nome_mes.upper()})", kpi_label),
                Paragraph("CATÁLOGO DE MATERIAIS", kpi_label)
            ],
            [
                Paragraph(f"{total_itens_sp} un", kpi_val),
                Paragraph(f"{total_itens_st} un", kpi_val),
                Paragraph(f"{total_itens_sp + total_itens_st} un", kpi_val),
                Paragraph(f"{total_saidas_qtd} un", kpi_val),
                Paragraph(f"{len(dados_itens_estoque)} tipos", kpi_val)
            ],
            [
                Paragraph("Saldo disponível", kpi_sub),
                Paragraph("Saldo disponível", kpi_sub),
                Paragraph("Total nas 2 salas", kpi_sub),
                Paragraph(f"{total_saidas_registros} entregas realizadas", kpi_sub),
                Paragraph(f"{itens_com_baixo_estoque} em nível crítico", kpi_sub)
            ]
        ]
        kpi_table = Table(
            kpi_cells,
            colWidths=[156, 156, 156, 156, 156],
            style=TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('TOPPADDING', (0, 0), (-1, 0), 4),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
                ('TOPPADDING', (0, 1), (-1, 1), 1),
                ('BOTTOMPADDING', (0, 1), (-1, 1), 1),
                ('TOPPADDING', (0, 2), (-1, 2), 1),
                ('BOTTOMPADDING', (0, 2), (-1, 2), 4),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ])
        )
        elements.append(kpi_table)
        elements.append(Spacer(1, 10))

        # ==================================================================
        # SEÇÃO 1: POSIÇÃO ATUAL DE ESTOQUE POR SALA
        # ==================================================================
        elements.append(Paragraph(
            "1. Posição Atual de Estoque por Sala (Almoxarifado TI)",
            section_heading
        ))

        # Larguras: total 780 pt
        widths_p1 = [200, 115, 45, 65, 110, 110, 75, 60]
        headers_p1 = [
            Paragraph("Item / Material", th_style),
            Paragraph("Categoria", th_style),
            Paragraph("Unid.", th_center),
            Paragraph("Est. Mín.", th_center),
            Paragraph("Sala Principal", th_center),
            Paragraph("Sala 3º Andar", th_center),
            Paragraph("Saldo Total", th_center),
            Paragraph("Situação", th_center)
        ]
        table_data_p1 = [headers_p1]

        if dados_itens_estoque:
            for item in dados_itens_estoque:
                status_p = Paragraph("Atenção" if item['baixo'] else "Normal", td_warning if item['baixo'] else td_success)
                row = [
                    Paragraph(f"<b>{item['nome']}</b>", td_style),
                    Paragraph(item['categoria'], td_style),
                    Paragraph(item['unidade'], td_center),
                    Paragraph(str(item['estoque_minimo']), td_center),
                    Paragraph(f"<b>{item['sp']}</b> {item['unidade']}", td_center),
                    Paragraph(f"<b>{item['st']}</b> {item['unidade']}", td_center),
                    Paragraph(f"<b>{item['total']}</b> {item['unidade']}", td_bold_center),
                    status_p
                ]
                table_data_p1.append(row)

            # Linha de totalização
            row_total = [
                Paragraph(f"<b>TOTAL CONSOLIDADO ({len(dados_itens_estoque)} materiais cadastrados)</b>", td_bold),
                Paragraph("—", td_center),
                Paragraph("—", td_center),
                Paragraph("—", td_center),
                Paragraph(f"<b>{total_itens_sp} un</b>", td_bold_center),
                Paragraph(f"<b>{total_itens_st} un</b>", td_bold_center),
                Paragraph(f"<b>{total_itens_sp + total_itens_st} un</b>", td_bold_center),
                Paragraph("—", td_center)
            ]
            table_data_p1.append(row_total)
        else:
            table_data_p1.append([
                Paragraph("Nenhum material cadastrado no catálogo ativo.", td_style),
                Paragraph("—", td_center), Paragraph("—", td_center), Paragraph("—", td_center),
                Paragraph("0 un", td_center), Paragraph("0 un", td_center), Paragraph("0 un", td_center),
                Paragraph("—", td_center)
            ])

        table_p1 = Table(
            table_data_p1,
            colWidths=widths_p1,
            style=criar_estilo_tabela_zebrada(len(table_data_p1), header_bg='#0f172a'),
            repeatRows=1
        )
        if dados_itens_estoque:
            table_p1.setStyle(TableStyle([
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
                ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#0f172a')),
            ]))

        elements.append(table_p1)

        # ==================================================================
        # QUEBRA PARA A PÁGINA 2: SAÍDAS DO MÊS VIGENTE
        # ==================================================================
        elements.append(PageBreak())

        elements.append(Paragraph(
            f"2. Registro de Saídas e Entregas de Materiais no Mês Vigente — {periodo_str}",
            title_style
        ))
        elements.append(Paragraph(
            f"Hub Central - SirReinato Brasfort — Almoxarifado TI | Período: <b>01/{mes:02d}/{ano}</b> a <b>{ultimo_dia:02d}/{mes:02d}/{ano}</b> | Total de saídas registradas: <b>{total_saidas_qtd} un</b> em <b>{total_saidas_registros} movimentações</b>",
            subtitle_style
        ))

        # Larguras: total 780 pt
        widths_p2 = [75, 140, 45, 95, 110, 105, 90, 120]
        headers_p2 = [
            Paragraph("Data/Hora", th_style),
            Paragraph("Material Retirado", th_style),
            Paragraph("Qtd", th_center),
            Paragraph("Sala Origem", th_style),
            Paragraph("Setor Solicitante", th_style),
            Paragraph("Recebido por", th_style),
            Paragraph("Entregue por", th_style),
            Paragraph("Observação / Motivo", th_style)
        ]
        table_data_p2 = [headers_p2]

        if saidas:
            for s in saidas:
                dt_str = s.created_at.strftime("%d/%m/%Y %H:%M") if s.created_at else "—"
                mat_nome = s.item.nome if s.item else f"Item #{s.item_id}"
                mat_un = s.item.unidade if s.item else "UN"
                qtd_str = f"<b>{s.quantidade}</b> {mat_un}"
                origem_str = s.sala_origem or "Sala Principal"
                setor_str = s.setor or "Geral"
                recebido_str = s.recebido_por or "—"
                entregue_str = s.entregue_por or "—"
                obs_str = s.observacao or "Atendimento padrão"

                row = [
                    Paragraph(dt_str, td_style),
                    Paragraph(f"<b>{mat_nome}</b>", td_style),
                    Paragraph(qtd_str, td_center),
                    Paragraph(origem_str, td_style),
                    Paragraph(setor_str, td_style),
                    Paragraph(recebido_str, td_style),
                    Paragraph(entregue_str, td_style),
                    Paragraph(obs_str, td_style)
                ]
                table_data_p2.append(row)

            # Linha de totalização de saídas
            row_total_saidas = [
                Paragraph("<b>TOTAL DE UNIDADES ENTREGUES NO MÊS:</b>", td_bold),
                Paragraph("—", td_center),
                Paragraph(f"<b>{total_saidas_qtd} un</b>", td_bold_center),
                Paragraph("—", td_center),
                Paragraph("—", td_center),
                Paragraph("—", td_center),
                Paragraph("—", td_center),
                Paragraph(f"<b>{total_saidas_registros} movimentações registradas</b>", td_bold)
            ]
            table_data_p2.append(row_total_saidas)
        else:
            table_data_p2.append([
                Paragraph("—", td_center),
                Paragraph(f"Nenhuma saída de material foi registrada para o almoxarifado no mês de {periodo_str}.", td_style),
                Paragraph("0", td_center),
                Paragraph("—", td_center),
                Paragraph("—", td_center),
                Paragraph("—", td_center),
                Paragraph("—", td_center),
                Paragraph("—", td_center)
            ])

        table_p2 = Table(
            table_data_p2,
            colWidths=widths_p2,
            style=criar_estilo_tabela_zebrada(len(table_data_p2), header_bg='#0f172a'),
            repeatRows=1
        )
        if saidas:
            table_p2.setStyle(TableStyle([
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
                ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#0f172a')),
            ]))

        elements.append(table_p2)

        # ==================================================================
        # SEÇÃO 3: RESUMO ANALÍTICO (SETORES E MATERIAIS DEMANDADOS)
        # ==================================================================
        if saidas and (setores_ranking or materiais_ranking):
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(
                "3. Resumo Analítico de Demandas do Mês",
                section_heading
            ))

            # Tabela Setores (largura 380) e Materiais (largura 380) lado a lado
            col_w_analitica = [250, 70, 60]

            # Dados setores
            headers_setores = [
                Paragraph("Setor Atendido", th_style),
                Paragraph("Qtd Retirada", th_center),
                Paragraph("% Mês", th_center)
            ]
            data_setores = [headers_setores]
            for setor, qtd in setores_ranking[:6]:
                pct = (qtd / total_saidas_qtd * 100) if total_saidas_qtd > 0 else 0
                data_setores.append([
                    Paragraph(f"<b>{setor}</b>", td_style),
                    Paragraph(f"{qtd} un", td_center),
                    Paragraph(f"{pct:.1f}%", td_center)
                ])

            table_setores = Table(
                data_setores,
                colWidths=col_w_analitica,
                style=criar_estilo_tabela_zebrada(len(data_setores), header_bg='#334155')
            )

            # Dados materiais
            headers_materiais = [
                Paragraph("Material Requisitado", th_style),
                Paragraph("Qtd Retirada", th_center),
                Paragraph("% Mês", th_center)
            ]
            data_materiais = [headers_materiais]
            for mat, qtd in materiais_ranking[:6]:
                pct = (qtd / total_saidas_qtd * 100) if total_saidas_qtd > 0 else 0
                data_materiais.append([
                    Paragraph(f"<b>{mat}</b>", td_style),
                    Paragraph(f"{qtd} un", td_center),
                    Paragraph(f"{pct:.1f}%", td_center)
                ])

            table_materiais = Table(
                data_materiais,
                colWidths=col_w_analitica,
                style=criar_estilo_tabela_zebrada(len(data_materiais), header_bg='#334155')
            )

            # Envelopa as duas tabelas lado a lado numa tabela container de 780 pt
            tabela_container = Table(
                [
                    [
                        Paragraph("<b>Top Setores Solicitantes:</b>", td_bold),
                        Paragraph("<b>Top Materiais Mais Retirados:</b>", td_bold)
                    ],
                    [table_setores, table_materiais]
                ],
                colWidths=[385, 395],
                style=TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ])
            )
            elements.append(tabela_container)

        doc.build(elements, canvasmaker=ItensSalaNumberedCanvas)
        buf.seek(0)
        return buf

