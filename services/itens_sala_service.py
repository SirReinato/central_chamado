import logging
from datetime import datetime, timedelta
from sqlalchemy import func, or_, desc
from models import db, ItemSala, ItemSalaEstoque, ItemSalaMovimentacao, Usuario

logger = logging.getLogger('central_chamados')


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
