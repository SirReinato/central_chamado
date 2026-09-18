from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Impressora
from services.impressoras_services import ImpressorasService
from services.suprimentos_services import SuprimentosService
from utils.decorator import staff_required

impressoras_bp = Blueprint(
    "impressoras",
    __name__,
    url_prefix="/impressoras"
)

@impressoras_bp.route("/")
@login_required
@staff_required
def index():
    busca = request.args.get("busca", "").strip()
    status_filtro = request.args.get("status", "").strip()
    suprimento_filtro = request.args.get("suprimento", "").strip()
    page = request.args.get("page", 1, type=int)

    # Métricas globais sobre o parque de impressão (independentes do filtro ativo)
    total_impressoras = Impressora.query.count()
    total_online = Impressora.query.filter_by(online=True).count()
    total_offline = Impressora.query.filter_by(online=False).count()

    pagination = ImpressorasService.listar_impressoras_paginadas(
        busca=busca,
        status_filtro=status_filtro,
        suprimento_filtro=suprimento_filtro,
        page=page,
        per_page=12
    )

    familias = SuprimentosService.listar_familias()

    return render_template(
        "impressoras/impressoras.html",
        impressoras=pagination.items,
        pagination=pagination,
        familias=familias,
        total_impressoras=total_impressoras,
        total_online=total_online,
        total_offline=total_offline,
        filtros={
            "busca": busca,
            "status": status_filtro,
            "suprimento": suprimento_filtro
        }
    )
    
@impressoras_bp.route("/nova", methods=["GET", "POST"])
@login_required
@staff_required
def nova_impressora():

    if request.method == "POST":
        nome = request.form.get("nome")
        ip = request.form.get("ip")
        modelo = request.form.get("modelo")

        ImpressorasService.adicionar_impressora(
            nome,
            ip,
            modelo
        )
        flash("Impressora adicionada com sucesso!", "success")
        return redirect(
            url_for("impressoras.index")
        )

    return render_template(
        "impressoras/nova_impressora.html"
    )

@impressoras_bp.route("/descobrir", methods=["GET", "POST"])
@login_required
@staff_required
def descobrir_impressoras():
    ImpressorasService.descobrir_impressoras()
    flash("Varredura de descoberta finalizada.", "success")
    return redirect(
        url_for("impressoras.index")
    )
    
@impressoras_bp.route("/sincronizar", methods=["GET", "POST"])
@login_required
@staff_required
def sincronizar():
    ImpressorasService.sincronizar_dc1()
    ImpressorasService.atualizar_ips_dc1()
    ImpressorasService.atualizar_status()
    flash("Sincronização realizada com sucesso!", "success")
    return redirect(
        url_for("impressoras.index")
    )
    
@impressoras_bp.route("/atualizar-status", methods=["GET", "POST"])
@login_required
@staff_required
def atualizar_status():
    ImpressorasService.atualizar_status()
    flash("Status das impressoras atualizado!", "success")
    return redirect(
        url_for("impressoras.index")
    )
    
@impressoras_bp.route("/teste-web")
@login_required
@staff_required
def teste_web():
    resultado = ImpressorasService.consultar_interface_web(
        "10.90.1.16"
    )
    return resultado


# ==========================================
# ROTAS: CONTROLE DE ESTOQUE E SUPRIMENTOS
# ==========================================

@impressoras_bp.route('/estoque')
@login_required
@staff_required
def gerenciar_estoque():
    page = request.args.get('page', 1, type=int)
    familias = SuprimentosService.listar_familias()
    historico_pagination = SuprimentosService.listar_historico_paginado(page=page, per_page=15)
    return render_template(
        'impressoras/estoque.html',
        familias=familias,
        historico=historico_pagination.items,
        historico_pagination=historico_pagination
    )

@impressoras_bp.route('/estoque/criar', methods=['POST'])
@login_required
@staff_required
def criar_familia():
    nome = request.form.get('nome_familia')
    toner = request.form.get('quantidade_toner', 0)
    cilindro = request.form.get('quantidade_cilindro', 0)
    minimo = request.form.get('estoque_minimo', 2)

    _, mensagem = SuprimentosService.criar_familia(nome, toner, cilindro, minimo)
    flash(mensagem, 'success' if 'sucesso' in mensagem.lower() else 'danger')
    return redirect(url_for('impressoras.gerenciar_estoque'))

@impressoras_bp.route('/estoque/adicionar/<int:familia_id>', methods=['POST'])
@login_required
@staff_required
def adicionar_estoque(familia_id):
    toner_add = request.form.get('toner_add', 0)
    cilindro_add = request.form.get('cilindro_add', 0)

    sucesso, mensagem = SuprimentosService.adicionar_estoque(familia_id, toner_add, cilindro_add)
    flash(mensagem, 'success' if sucesso else 'danger')
    return redirect(url_for('impressoras.gerenciar_estoque'))

@impressoras_bp.route('/retirar/<int:impressora_id>', methods=['POST'])
@login_required
@staff_required
def retirar_insumo(impressora_id):
    tipo_insumo = request.form.get('tipo_insumo') # 'toner' ou 'cilindro'
    usuario_nome = current_user.nome if hasattr(current_user, 'nome') else 'Sistema'

    sucesso, mensagem = SuprimentosService.retirar_insumo(impressora_id, tipo_insumo, usuario_nome)
    flash(mensagem, 'success' if sucesso else 'danger')
    return redirect(url_for('impressoras.index'))

@impressoras_bp.route('/vincular/<int:impressora_id>', methods=['POST'])
@login_required
@staff_required
def vincular_impressora(impressora_id):
    impressora = db.session.get(Impressora, impressora_id)
    if not impressora:
        flash("Impressora não encontrada.", "danger")
        return redirect(url_for('impressoras.index'))

    impressora.andar = request.form.get('andar', impressora.andar)
    impressora.sala = request.form.get('sala', impressora.sala)
    
    suprimento_id = request.form.get('suprimento_id')
    try:
        impressora.suprimento_id = int(suprimento_id) if suprimento_id else None
    except (ValueError, TypeError):
        impressora.suprimento_id = None

    db.session.commit()
    flash(f"Vínculo e localização da impressora {impressora.nome} atualizados com sucesso!", "success")
    return redirect(url_for('impressoras.index'))


@impressoras_bp.route('/estoque/ajustar/<int:familia_id>', methods=['POST'])
@login_required
@staff_required
def ajustar_estoque(familia_id):
    tipo_insumo = request.form.get('tipo_insumo')
    operacao = request.form.get('operacao')  # 'add' ou 'remove'
    quantidade = request.form.get('quantidade', 0)
    motivo = request.form.get('motivo', 'Não informado')
    usuario_nome = current_user.nome if hasattr(current_user, 'nome') else 'Sistema'

    try:
        quantidade = int(quantidade)
    except (TypeError, ValueError):
        quantidade = 0

    if operacao == 'remove':
        quantidade = -abs(quantidade)
    else:
        quantidade = abs(quantidade)

    sucesso, mensagem = SuprimentosService.ajustar_estoque(
        familia_id, tipo_insumo, quantidade, motivo, usuario_nome
    )
    flash(mensagem, 'success' if sucesso else 'danger')
    return redirect(url_for('impressoras.gerenciar_estoque'))