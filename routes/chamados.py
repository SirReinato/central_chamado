from datetime import datetime
from flask import Blueprint, render_template, request, redirect, abort, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import case

from models import db, Chamado

from services.chamado_service import (
    criar_chamado,
    buscar_chamado_por_id,
    excluir_chamado as deletar_chamado_service
)

from services.impressoras_services import ImpressorasService

from utils.decorator import admin_required, staff_required



chamados_bp = Blueprint(
    'chamados',
    __name__
)


# =============================================================
# CONSULTAS
# =============================================================

def query_chamados():
    """
    Retorna a consulta de chamados de acordo com o usuário logado.

    Administradores:
        Retornam todos os chamados.

    Usuários comuns:
        Retornam apenas os chamados pertencentes ao usuário.
    """

    if current_user.is_admin or current_user.is_operador:
        return Chamado.query

    return Chamado.query.filter_by(
        usuario_id=current_user.id
    )


def lista_de_chamados():
    """
    Lista os chamados ordenados por prioridade de status.
    """

    ordem_status = case(
        (Chamado.status == 'Aberto', 1),
        (Chamado.status == 'Em Atendimento', 2),
        (Chamado.status == 'Pendente', 3),
        (Chamado.status == 'Resolvido', 4),
        (Chamado.status == 'Fechado', 5),
        else_=6
    )

    return query_chamados().order_by(
        ordem_status,
        Chamado.data_abertura.desc()
    ).all()


# =============================================================
# HOME
# =============================================================

@chamados_bp.route('/home')
@login_required
def home():

    total = query_chamados().count()

    abertos = query_chamados().filter_by(
        status='Aberto'
    ).count()

    em_atendimento = query_chamados().filter_by(
        status='Em Atendimento'
    ).count()

    resolvidos = query_chamados().filter_by(
        status='Resolvido'
    ).count()

    fechados = query_chamados().filter_by(
        status='Fechado'
    ).count()

    chamados_abertos = query_chamados().filter_by(
        status='Aberto'
    ).order_by(
        Chamado.data_abertura.desc()
    ).limit(5).all()

    itens_atencao = ImpressorasService.obter_itens_atencao()

    return render_template(
        'index.html',
        total=total,
        abertos=abertos,
        em_atendimento=em_atendimento,
        resolvidos=resolvidos,
        fechados=fechados,
        chamados_abertos=chamados_abertos,
        itens_atencao=itens_atencao
    )


# =============================================================
# LISTAGEM DE CHAMADOS (COM FILTROS E PAGINAÇÃO)
# =============================================================

@chamados_bp.route('/chamados')
@login_required
def listar_chamados():
    busca = request.args.get('busca', '').strip()
    status = request.args.get('status', '').strip()
    prioridade = request.args.get('prioridade', '').strip()
    categoria = request.args.get('categoria', '').strip()
    page = request.args.get('page', 1, type=int)

    query = query_chamados()

    if busca:
        termo_id = busca.lstrip('#')
        if termo_id.isdigit():
            query = query.filter(
                db.or_(
                    Chamado.id == int(termo_id),
                    Chamado.titulo.ilike(f'%{busca}%'),
                    Chamado.solicitante.ilike(f'%{busca}%'),
                    Chamado.setor.ilike(f'%{busca}%'),
                    Chamado.descricao.ilike(f'%{busca}%')
                )
            )
        else:
            termo = f'%{busca}%'
            query = query.filter(
                db.or_(
                    Chamado.titulo.ilike(termo),
                    Chamado.solicitante.ilike(termo),
                    Chamado.setor.ilike(termo),
                    Chamado.descricao.ilike(termo)
                )
            )

    if status:
        query = query.filter(Chamado.status == status)

    if prioridade:
        query = query.filter(Chamado.prioridade == prioridade)

    if categoria:
        query = query.filter(Chamado.categoria == categoria)

    ordem_status = case(
        (Chamado.status == 'Aberto', 1),
        (Chamado.status == 'Em Atendimento', 2),
        (Chamado.status == 'Pendente', 3),
        (Chamado.status == 'Resolvido', 4),
        (Chamado.status == 'Fechado', 5),
        else_=6
    )

    pagination = query.order_by(
        ordem_status,
        Chamado.data_abertura.desc()
    ).paginate(page=page, per_page=10, error_out=False)

    return render_template(
        'chamados/listar_chamados.html',
        chamados=pagination.items,
        pagination=pagination,
        filtros={
            'busca': busca,
            'status': status,
            'prioridade': prioridade,
            'categoria': categoria
        }
    )


# =============================================================
# NOVO CHAMADO
# =============================================================

@chamados_bp.route('/chamados/novo', methods=['GET', 'POST'])
@login_required
def novo_chamado():

    if request.method == 'POST':

        chamado = criar_chamado(request.form)
        flash(f"Chamado #{chamado.id} criado com sucesso!", "success")

        return redirect(
            url_for('chamados.listar_chamados')
        )

    return render_template(
        'chamados/novo_chamado.html'
    )


# =============================================================
# EDITAR CHAMADO
# =============================================================

@chamados_bp.route('/chamados/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_chamado(id):

    chamado = buscar_chamado_por_id(id)

    # Usuário comum só pode editar seus próprios chamados
    if (
        not (current_user.is_admin or current_user.is_operador)
        and chamado.usuario_id != current_user.id
    ):
        abort(403)

    if request.method == 'POST':

        chamado.solicitante = request.form.get('solicitante', chamado.solicitante).strip()
        chamado.setor = request.form.get('setor', chamado.setor).strip()
        chamado.titulo = request.form.get('titulo', chamado.titulo).strip()
        chamado.descricao = request.form.get('descricao', chamado.descricao).strip()
        chamado.categoria = request.form.get('categoria', chamado.categoria)
        chamado.data_atualizacao = datetime.now()

        # Apenas admin ou operador podem alterar status e prioridade
        if current_user.is_admin or current_user.is_operador:
            chamado.prioridade = request.form.get('prioridade', chamado.prioridade)
            novo_status = request.form.get('status', chamado.status)
            if novo_status in ('Resolvido', 'Fechado') and chamado.status not in ('Resolvido', 'Fechado'):
                chamado.data_fechamento = datetime.now()
                if not chamado.tecnico_id:
                    chamado.tecnico_id = current_user.id
            chamado.status = novo_status

        db.session.commit()
        flash(f"Chamado #{chamado.id} atualizado com sucesso!", "success")

        return redirect(
            url_for('chamados.detalhes_chamado', id=chamado.id)
        )

    return render_template(
        'chamados/editar_chamado.html',
        chamado=chamado
    )


# =============================================================
# EXCLUIR CHAMADO
# =============================================================

@chamados_bp.route('/chamados/excluir/<int:id>', methods=['POST', 'GET'])
@login_required
@admin_required
def excluir_chamado(id):

    deletar_chamado_service(id)
    flash(f"Chamado #{id} excluído com sucesso.", "warning")

    return redirect(
        url_for('chamados.listar_chamados')
    )


# =============================================================
# DETALHES DO CHAMADO
# =============================================================

@chamados_bp.route('/chamados/detalhes/<int:id>')
@login_required
def detalhes_chamado(id):

    chamado = buscar_chamado_por_id(id)

    # Usuário comum só pode visualizar seus próprios chamados
    if (
        not (current_user.is_admin or current_user.is_operador)
        and chamado.usuario_id != current_user.id
    ):
        abort(403)

    return render_template(
        'chamados/detalhes_chamado.html',
        chamado=chamado
    )


# =============================================================
# RESOLVER CHAMADO
# =============================================================

@chamados_bp.route('/chamados/resolver/<int:id>', methods=['POST', 'GET'])
@login_required
@staff_required
def resolver_chamado(id):

    chamado = buscar_chamado_por_id(id)

    chamado.status = 'Resolvido'
    chamado.data_fechamento = datetime.now()
    chamado.data_atualizacao = datetime.now()
    if not chamado.tecnico_id:
        chamado.tecnico_id = current_user.id

    db.session.commit()
    flash(f"Chamado #{chamado.id} marcado como Resolvido!", "success")

    return redirect(
        url_for('chamados.detalhes_chamado', id=chamado.id)
    )


# =============================================================
# FECHAR CHAMADO
# =============================================================

@chamados_bp.route('/chamados/fechar/<int:id>', methods=['POST', 'GET'])
@login_required
@staff_required
def fechar_chamado(id):

    chamado = buscar_chamado_por_id(id)

    chamado.status = 'Fechado'
    chamado.data_fechamento = datetime.now()
    chamado.data_atualizacao = datetime.now()
    if not chamado.tecnico_id:
        chamado.tecnico_id = current_user.id

    db.session.commit()
    flash(f"Chamado #{chamado.id} encerrado com sucesso!", "info")

    return redirect(
        url_for('chamados.detalhes_chamado', id=chamado.id)
    )