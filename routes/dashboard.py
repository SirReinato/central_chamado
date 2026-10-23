from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from datetime import datetime, timedelta

from models import Usuario, Chamado, Ramal, EstoqueSuprimento
from services.impressoras_services import ImpressorasService


dashboard_bp = Blueprint(
    'dashboard',
    __name__
)


def _ranking(query, coluna, limite=None):
    """
    Agrupa os chamados da query por uma coluna (categoria, setor, etc.)
    e devolve uma lista pronta para o template, ja com o percentual
    relativo ao maior grupo (usado para desenhar a barra).
    """

    consulta = query.with_entities(
        coluna, func.count(Chamado.id)
    ).filter(
        coluna.isnot(None)
    ).group_by(
        coluna
    ).order_by(
        func.count(Chamado.id).desc()
    )

    if limite:
        consulta = consulta.limit(limite)

    resultados = consulta.all()

    maior = max((qtd for _, qtd in resultados), default=0)

    return [
        {
            'nome': nome,
            'total': qtd,
            'percentual': round((qtd / maior) * 100) if maior else 0
        }
        for nome, qtd in resultados
    ]


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_tecnico_impressora:
        return redirect(url_for('impressoras.index'))

    query = Chamado.query

    if not current_user.is_admin:
        query = query.filter_by(
            usuario_id=current_user.id
        )

    total = query.count()

    abertos = query.filter(
        Chamado.status.in_(['Aberto', 'Novo'])
    ).count()

    em_atendimento = query.filter(
        Chamado.status.in_([
            'Em Atendimento',
            'Pendente'
        ])
    ).count()

    resolvidos = query.filter_by(
        status='Resolvido'
    ).count()

    fechados = query.filter_by(
        status='Fechado'
    ).count()

    # Chamados recentes (ultimos 5)
    chamados_recentes = query.order_by(
        desc(Chamado.data_abertura)
    ).limit(5).all()

    if current_user.is_admin:
        usuarios = Usuario.query.order_by(
            Usuario.nome
        ).all()
        total_usuarios = Usuario.query.count()
        usuarios_pendentes = [u for u in usuarios if u.status == 'pendente'][:5]
    else:
        usuarios = [current_user]
        total_usuarios = 1
        usuarios_pendentes = []

    por_categoria = _ranking(query, Chamado.categoria)
    por_setor = _ranking(query, Chamado.setor, limite=5)

    # Itens críticos de impressoras/suprimentos (só admin)
    itens_atencao = (
        ImpressorasService.obter_itens_atencao()
        if current_user.is_admin
        else []
    )

    # Ramais favoritos (todos veem)
    ramais_favoritos = Ramal.query.order_by(
        Ramal.departamento, Ramal.nome
    ).limit(5).all()

    # Estoque crítico (só admin)
    estoque_critico = []
    if current_user.is_admin:
        estoque_critico = EstoqueSuprimento.query.filter(
            (EstoqueSuprimento.quantidade_toner <= EstoqueSuprimento.estoque_minimo) |
            (EstoqueSuprimento.quantidade_cilindro <= EstoqueSuprimento.estoque_minimo)
        ).all()

    # Tendencia chamados últimos 7 dias (só admin)
    tendencia_chamados = []
    if current_user.is_admin:
        sete_dias_atras = datetime.now() - timedelta(days=7)
        tendencia = (
            Chamado.query
            .filter(Chamado.data_abertura >= sete_dias_atras)
            .with_entities(
                func.strftime('%d/%m', Chamado.data_abertura).label('dia'),
                func.count(Chamado.id).label('qtd')
            )
            .group_by(func.strftime('%d/%m', Chamado.data_abertura))
            .order_by(func.strftime('%d/%m', Chamado.data_abertura))
            .all()
        )
        tendencia_chamados = [{'dia': d, 'qtd': q} for d, q in tendencia]

    # Notificações (chamados meus em aberto)
    notificacoes = 0
    if not current_user.is_admin:
        notificacoes = query.filter(
            Chamado.status.in_(['Aberto', 'Em Atendimento', 'Pendente'])
        ).count()

    return render_template(
        'dashboard.html',
        total=total,
        abertos=abertos,
        em_atendimento=em_atendimento,
        resolvidos=resolvidos,
        fechados=fechados,
        usuarios=usuarios,
        total_usuarios=total_usuarios,
        usuarios_pendentes=usuarios_pendentes,
        por_categoria=por_categoria,
        por_setor=por_setor,
        itens_atencao=itens_atencao,
        chamados_recentes=chamados_recentes,
        ramais_favoritos=ramais_favoritos,
        estoque_critico=estoque_critico,
        tendencia_chamados=tendencia_chamados,
        notificacoes=notificacoes,
        pode_gerenciar=current_user.is_admin
    )


@dashboard_bp.route('/api/tendencia-chamados')
@login_required
def api_tendencia_chamados():
    """API para grafico de tendencia (AJAX)."""
    if not current_user.is_admin:
        return jsonify({'error': 'Acesso negado'}), 403

    sete_dias_atras = datetime.now() - timedelta(days=7)
    tendencia = (
        Chamado.query
        .filter(Chamado.data_abertura >= sete_dias_atras)
        .with_entities(
            func.strftime('%d/%m', Chamado.data_abertura).label('dia'),
            func.count(Chamado.id).label('qtd')
        )
        .group_by(func.strftime('%d/%m', Chamado.data_abertura))
        .order_by(func.strftime('%d/%m', Chamado.data_abertura))
        .all()
    )
    return jsonify([{'dia': d, 'qtd': q} for d, q in tendencia])
