from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Impressora
from services.impressoras_services import ImpressorasService
from services.suprimentos_services import SuprimentosService

impressoras_bp = Blueprint(
    "impressoras",
    __name__,
    url_prefix="/impressoras"
)

@impressoras_bp.route("/")
@login_required
def index():
    impressoras = ImpressorasService.listar_impressoras()
    familias = SuprimentosService.listar_familias()
    
    return render_template(
        "impressoras/impressoras.html",
        impressoras=impressoras,
        familias=familias
    )
    
@impressoras_bp.route("/nova", methods=["GET", "POST"])
@login_required
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

@impressoras_bp.route("/descobrir")
@login_required
def descobrir_impressoras():
    ImpressorasService.descobrir_impressoras()
    flash("Varredura de descoberta finalizada.", "success")
    return redirect(
        url_for("impressoras.index")
    )
    
@impressoras_bp.route("/sincronizar")
@login_required
def sincronizar():
    ImpressorasService.sincronizar_dc1()
    ImpressorasService.atualizar_ips_dc1()
    ImpressorasService.atualizar_status()
    flash("Sincronização realizada com sucesso!", "success")
    return redirect(
        url_for("impressoras.index")
    )
    
@impressoras_bp.route("/atualizar-status")
@login_required
def atualizar_status():
    ImpressorasService.atualizar_status()
    flash("Status das impressoras atualizado!", "success")
    return redirect(
        url_for("impressoras.index")
    )
    
@impressoras_bp.route("/teste-web")
@login_required
def teste_web():
    resultado = ImpressorasService.consultar_interface_web(
        "10.90.1.16"
    )
    return resultado


# ==========================================
# NOVAS ROTAS: CONTROLE DE ESTOQUE E SUPRIMENTOS
# ==========================================

@impressoras_bp.route('/estoque')
@login_required
def gerenciar_estoque():
    familias = SuprimentosService.listar_familias()
    historico = SuprimentosService.listar_historico(limite=30)
    return render_template('impressoras/estoque.html', familias=familias, historico=historico)

@impressoras_bp.route('/estoque/criar', methods=['POST'])
@login_required
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
def adicionar_estoque(familia_id):
    toner_add = request.form.get('toner_add', 0)
    cilindro_add = request.form.get('cilindro_add', 0)

    sucesso, mensagem = SuprimentosService.adicionar_estoque(familia_id, toner_add, cilindro_add)
    flash(mensagem, 'success' if sucesso else 'danger')
    return redirect(url_for('impressoras.gerenciar_estoque'))

@impressoras_bp.route('/retirar/<int:impressora_id>', methods=['POST'])
@login_required
def retirar_insumo(impressora_id):
    tipo_insumo = request.form.get('tipo_insumo') # 'toner' ou 'cilindro'
    usuario_nome = current_user.nome if hasattr(current_user, 'nome') else 'Sistema'

    sucesso, mensagem = SuprimentosService.retirar_insumo(impressora_id, tipo_insumo, usuario_nome)
    flash(mensagem, 'success' if sucesso else 'danger')
    return redirect(url_for('impressoras.index'))

@impressoras_bp.route('/vincular/<int:impressora_id>', methods=['POST'])
@login_required
def vincular_impressora(impressora_id):
    impressora = db.session.get(Impressora, impressora_id)
    if not impressora:
        flash("Impressora não encontrada.", "danger")
        return redirect(url_for('impressoras.index'))

    impressora.andar = request.form.get('andar', impressora.andar)
    impressora.sala = request.form.get('sala', impressora.sala)
    
    suprimento_id = request.form.get('suprimento_id')
    impressora.suprimento_id = int(suprimento_id) if suprimento_id else None

    db.session.commit()
    flash(f"Vínculo e localização da impressora {impressora.nome} atualizados com sucesso!", "success")
    return redirect(url_for('impressoras.index'))


@impressoras_bp.route('/estoque/ajustar/<int:familia_id>', methods=['POST'])
@login_required
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