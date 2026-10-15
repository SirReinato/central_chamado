import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from services.itens_sala_service import ItensSalaService
from utils.decorator import printer_staff_required
from models import ItemSala

itens_sala_bp = Blueprint('itens_sala', __name__, url_prefix='/itens-sala')


@itens_sala_bp.route('/', methods=['GET'])
@login_required
@printer_staff_required
def index():
    """Página principal da Central de Itens da Sala (Almoxarifado TI)."""
    # Parâmetros de filtro
    busca = request.args.get('busca', '').strip()
    categoria = request.args.get('categoria', 'todas').strip()
    tab_ativa = request.args.get('tab', 'salas').strip()

    # Filtros da Timeline de Histórico
    tipo_historico = request.args.get('tipo_hist', 'todos').strip()
    sala_historico = request.args.get('sala_hist', 'todas').strip()
    setor_historico = request.args.get('setor_hist', '').strip()
    busca_historico = request.args.get('busca_hist', '').strip()
    data_inicio = request.args.get('data_inicio', '').strip()
    data_fim = request.args.get('data_fim', '').strip()

    # Carrega dados
    kpis = ItensSalaService.obter_kpis()
    salas_dados = ItensSalaService.obter_resumo_por_sala(busca=busca, categoria=categoria)
    todos_itens = ItensSalaService.listar_todos_itens()
    historico = ItensSalaService.obter_historico(
        tipo=tipo_historico,
        sala=sala_historico,
        setor=setor_historico,
        busca=busca_historico,
        data_inicio=data_inicio,
        data_fim=data_fim,
        limite=150
    )
    graficos_dados = ItensSalaService.obter_dados_graficos()

    filtros = {
        'busca': busca,
        'categoria': categoria,
        'tab': tab_ativa,
        'tipo_hist': tipo_historico,
        'sala_hist': sala_historico,
        'setor_hist': setor_historico,
        'busca_hist': busca_historico,
        'data_inicio': data_inicio,
        'data_fim': data_fim
    }

    return render_template(
        'itens_sala/index.html',
        kpis=kpis,
        salas_dados=salas_dados,
        todos_itens=todos_itens,
        categorias=ItensSalaService.CATEGORIAS_PADRAO,
        origens_entrada=ItensSalaService.ORIGENS_ENTRADA,
        salas_validas=ItensSalaService.SALAS_VALIDAS,
        historico=historico,
        graficos_json=json.dumps(graficos_dados),
        filtros=filtros
    )


@itens_sala_bp.route('/novo', methods=['POST'])
@login_required
@printer_staff_required
def novo_item():
    """Cadastra um novo material no catálogo."""
    try:
        nome = request.form.get('nome')
        categoria = request.form.get('categoria')
        estoque_minimo = request.form.get('estoque_minimo', 2)
        sala_inicial = request.form.get('sala_inicial', ItensSalaService.SALA_PRINCIPAL)
        qtd_inicial = request.form.get('quantidade_inicial', 0)
        unidade = request.form.get('unidade', 'UN')
        descricao = request.form.get('descricao')

        item = ItensSalaService.criar_item(
            nome=nome,
            categoria=categoria,
            estoque_minimo=estoque_minimo,
            sala_inicial=sala_inicial,
            qtd_inicial=qtd_inicial,
            descricao=descricao,
            unidade=unidade,
            usuario_id=current_user.id
        )
        flash(f"Material '{item.nome}' cadastrado com sucesso!", "success")
    except ValueError as ve:
        flash(str(ve), "danger")
    except Exception as e:
        flash(f"Erro inesperado ao cadastrar item: {e}", "danger")

    return redirect(url_for('itens_sala.index'))


@itens_sala_bp.route('/saida', methods=['POST'])
@login_required
@printer_staff_required
def registrar_saida():
    """Registra retirada de item de uma sala."""
    try:
        item_id = int(request.form.get('item_id'))
        sala = request.form.get('sala')
        quantidade = int(request.form.get('quantidade', 1))
        entregue_por = request.form.get('entregue_por') or current_user.nome
        recebido_por = request.form.get('recebido_por')
        setor = request.form.get('setor')
        observacao = request.form.get('observacao')

        mov = ItensSalaService.registrar_saida(
            item_id=item_id,
            sala=sala,
            quantidade=quantidade,
            entregue_por=entregue_por,
            recebido_por=recebido_por,
            setor=setor,
            observacao=observacao,
            usuario_id=current_user.id
        )
        flash(f"Saída de {quantidade}x '{mov.item.nome}' da {sala} registrada para '{recebido_por}' ({setor})!", "success")
    except ValueError as ve:
        flash(str(ve), "danger")
    except Exception as e:
        flash(f"Erro ao registrar saída: {e}", "danger")

    return redirect(url_for('itens_sala.index', tab='salas'))


@itens_sala_bp.route('/entrada', methods=['POST'])
@login_required
@printer_staff_required
def registrar_entrada():
    """Registra entrada/reposição de insumo em uma sala."""
    try:
        item_id = int(request.form.get('item_id'))
        sala = request.form.get('sala')
        quantidade = int(request.form.get('quantidade', 1))
        adicionado_por = request.form.get('adicionado_por') or current_user.nome
        origem = request.form.get('origem')
        observacao = request.form.get('observacao')

        mov = ItensSalaService.registrar_entrada(
            item_id=item_id,
            sala=sala,
            quantidade=quantidade,
            adicionado_por=adicionado_por,
            origem=origem,
            observacao=observacao,
            usuario_id=current_user.id
        )
        flash(f"Entrada de {quantidade}x '{mov.item.nome}' na {sala} concluída com sucesso!", "success")
    except ValueError as ve:
        flash(str(ve), "danger")
    except Exception as e:
        flash(f"Erro ao registrar entrada: {e}", "danger")

    return redirect(url_for('itens_sala.index', tab='salas'))


@itens_sala_bp.route('/transferir', methods=['POST'])
@login_required
@printer_staff_required
def transferir():
    """Registra transferência de material entre a Sala Principal e a Sala do 3º Andar."""
    try:
        item_id = int(request.form.get('item_id'))
        sala_origem = request.form.get('sala_origem')
        sala_destino = request.form.get('sala_destino')
        quantidade = int(request.form.get('quantidade', 1))
        responsavel = request.form.get('responsavel') or current_user.nome
        motivo = request.form.get('motivo')

        mov = ItensSalaService.transferir_entre_salas(
            item_id=item_id,
            sala_origem=sala_origem,
            sala_destino=sala_destino,
            quantidade=quantidade,
            responsavel=responsavel,
            motivo=motivo,
            usuario_id=current_user.id
        )
        flash(f"Transferência de {quantidade}x '{mov.item.nome}' de {sala_origem} para {sala_destino} efetuada com sucesso!", "success")
    except ValueError as ve:
        flash(str(ve), "danger")
    except Exception as e:
        flash(f"Erro ao transferir itens: {e}", "danger")

    return redirect(url_for('itens_sala.index', tab='salas'))


@itens_sala_bp.route('/editar/<int:item_id>', methods=['POST'])
@login_required
@printer_staff_required
def editar_item(item_id):
    """Edita dados cadastrais de um material."""
    try:
        nome = request.form.get('nome')
        categoria = request.form.get('categoria')
        estoque_minimo = request.form.get('estoque_minimo')
        unidade = request.form.get('unidade')
        descricao = request.form.get('descricao')

        ItensSalaService.editar_item(
            item_id=item_id,
            nome=nome,
            categoria=categoria,
            estoque_minimo=estoque_minimo,
            descricao=descricao,
            unidade=unidade
        )
        flash("Dados do material atualizados com sucesso!", "success")
    except ValueError as ve:
        flash(str(ve), "danger")
    except Exception as e:
        flash(f"Erro ao atualizar material: {e}", "danger")

    return redirect(url_for('itens_sala.index'))


@itens_sala_bp.route('/excluir/<int:item_id>', methods=['POST'])
@login_required
@printer_staff_required
def excluir_item(item_id):
    """Desativa um material do catálogo."""
    try:
        ItensSalaService.excluir_item(item_id)
        flash("Material desativado com sucesso.", "info")
    except Exception as e:
        flash(f"Erro ao remover material: {e}", "danger")

    return redirect(url_for('itens_sala.index'))


@itens_sala_bp.route('/api/item/<int:item_id>', methods=['GET'])
@login_required
@printer_staff_required
def api_obter_item(item_id):
    """Retorna dados de estoque por sala do item para alimentar interações e limites dinâmicos no modal."""
    item = ItemSala.query.get(item_id)
    if not item or not item.ativo:
        return jsonify({'error': 'Item não encontrado'}), 404

    return jsonify({
        'id': item.id,
        'nome': item.nome,
        'categoria': item.categoria,
        'unidade': item.unidade,
        'estoque_minimo': item.estoque_minimo,
        'descricao': item.descricao or '',
        'total_estoque': item.total_estoque,
        'estoque_sala_principal': item.estoque_sala_principal,
        'estoque_sala_terceiro': item.estoque_sala_terceiro
    })
