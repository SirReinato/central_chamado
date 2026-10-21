from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_

from models import Ramal, db
from utils.decorator import admin_required


ramais_bp = Blueprint('ramais', __name__, url_prefix='/ramais')


# -------------------------------------------------------------------------
# LISTAGEM (Visualização liberada para todos os perfis autenticados)
# -------------------------------------------------------------------------
@ramais_bp.route('/', methods=['GET'])
@ramais_bp.route('', methods=['GET'])
@login_required
def index():
    """Página principal do módulo de Ramais Brasfort.

    Exibe a listagem organizada por Departamento/Setor com campo de busca rápida.
    Acesso: qualquer usuário autenticado.
    """
    busca = request.args.get('busca', '').strip()

    query = Ramal.query

    if busca:
        query = query.filter(
            or_(
                Ramal.nome.ilike(f'%{busca}%'),
                Ramal.departamento.ilike(f'%{busca}%'),
                Ramal.ramal.ilike(f'%{busca}%')
            )
        )

    ramais = query.order_by(Ramal.departamento.asc(), Ramal.nome.asc()).all()

    # Agrupa por departamento para exibição organizada
    from collections import defaultdict
    ramais_por_departamento = defaultdict(list)
    for r in ramais:
        ramais_por_departamento[r.departamento].append(r)

    # Ordena os departamentos alfabeticamente
    departamentos_ordenados = sorted(ramais_por_departamento.keys())

    return render_template(
        'ramais/index.html',
        ramais_por_departamento=dict(ramais_por_departamento),
        departamentos_ordenados=departamentos_ordenados,
        busca=busca,
        total=len(ramais),
        pode_gerenciar=current_user.is_admin
    )


# -------------------------------------------------------------------------
# API: Obter dados de um ramal (para preencher modal de edição)
# -------------------------------------------------------------------------
@ramais_bp.route('/api/<int:id>', methods=['GET'])
@login_required
def api_obter_ramal(id):
    """Retorna dados JSON de um ramal específico."""
    ramal = Ramal.query.get(id)
    if not ramal:
        return jsonify({'error': 'Ramal não encontrado'}), 404

    return jsonify(ramal.to_dict())


# -------------------------------------------------------------------------
# CRIAR (Restrito a administradores)
# -------------------------------------------------------------------------
@ramais_bp.route('/novo', methods=['POST'])
@login_required
@admin_required
def novo():
    """Cadastra um novo ramal."""
    nome = request.form.get('nome', '').strip()
    departamento = request.form.get('departamento', '').strip()
    numero_ramal = request.form.get('ramal', '').strip()
    andar = request.form.get('andar', '').strip() or None

    if not nome or not departamento or not numero_ramal:
        flash("Preencha todos os campos obrigatórios (Nome, Departamento e Ramal).", "warning")
        return redirect(url_for('ramais.index'))

    # Evita duplicidade de ramal para o mesmo colaborador/departamento
    existente = Ramal.query.filter_by(
        nome=nome,
        departamento=departamento,
        ramal=numero_ramal
    ).first()
    if existente:
        flash(f"Já existe um ramal '{numero_ramal}' cadasrado para '{nome}' no departamento '{departamento}'.", "warning")
        return redirect(url_for('ramais.index'))

    novo_ramal = Ramal(
        nome=nome,
        departamento=departamento,
        ramal=numero_ramal,
        andar=andar
    )
    db.session.add(novo_ramal)
    db.session.commit()

    flash(f"Ramal '{numero_ramal}' de '{nome}' cadastrado com sucesso!", "success")
    return redirect(url_for('ramais.index'))


# -------------------------------------------------------------------------
# EDITAR (Restrito a administradores)
# -------------------------------------------------------------------------
@ramais_bp.route('/editar/<int:id>', methods=['POST'])
@login_required
@admin_required
def editar(id):
    """Atualiza os dados de um ramal existente."""
    ramal = Ramal.query.get_or_404(id)

    nome = request.form.get('nome', '').strip()
    departamento = request.form.get('departamento', '').strip()
    numero_ramal = request.form.get('ramal', '').strip()
    andar = request.form.get('andar', '').strip() or None

    if not nome or not departamento or not numero_ramal:
        flash("Preencha todos os campos obrigatórios (Nome, Departamento e Ramal).", "warning")
        return redirect(url_for('ramais.index'))

    # Verifica duplicidade excluindo o próprio registro
    existente = Ramal.query.filter(
        Ramal.id != id,
        Ramal.nome == nome,
        Ramal.departamento == departamento,
        Ramal.ramal == numero_ramal
    ).first()
    if existente:
        flash(f"Já existe um ramal '{numero_ramal}' cadasrado para '{nome}' no departamento '{departamento}'.", "warning")
        return redirect(url_for('ramais.index'))

    ramal.nome = nome
    ramal.departamento = departamento
    ramal.ramal = numero_ramal
    ramal.andar = andar
    db.session.commit()

    flash(f"Ramal '{numero_ramal}' de '{nome}' atualizado com sucesso!", "success")
    return redirect(url_for('ramais.index'))


# -------------------------------------------------------------------------
# EXCLUIR (Restrito a administradores)
# -------------------------------------------------------------------------
@ramais_bp.route('/excluir/<int:id>', methods=['POST'])
@login_required
@admin_required
def excluir(id):
    """Exclui um ramal do diretório."""
    ramal = Ramal.query.get_or_404(id)

    nome_ramal = ramal.ramal
    nome_colaborador = ramal.nome

    db.session.delete(ramal)
    db.session.commit()

    flash(f"Ramal '{nome_ramal}' de '{nome_colaborador}' excluído com sucesso.", "info")
    return redirect(url_for('ramais.index'))
