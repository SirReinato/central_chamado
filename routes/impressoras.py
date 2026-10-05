from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from models import db, Impressora
from services.impressoras_services import ImpressorasService
from services.suprimentos_services import SuprimentosService
from utils.decorator import printer_staff_required

impressoras_bp = Blueprint(
    "impressoras",
    __name__,
    url_prefix="/impressoras"
)

@impressoras_bp.route("/")
@login_required
@printer_staff_required
def index():
    busca = request.args.get("busca", "").strip()
    status_filtro = request.args.get("status", "").strip()
    suprimento_filtro = request.args.get("suprimento", "").strip()
    tipo_filtro = request.args.get("tipo", "").strip()
    page = request.args.get("page", 1, type=int)

    # Se status for informado pelo dropdown ou atalho e page não foi explicitada
    if status_filtro == "offline" and "page" not in request.args:
        page = 2
    elif status_filtro == "online" and "page" not in request.args:
        page = 1

    if page not in [1, 2]:
        page = 1

    # Define o status_filtro efetivo para sincronia com a página
    if not status_filtro:
        status_filtro = "online" if page == 1 else "offline"

    # Métricas globais sobre o parque de impressão (independentes do filtro ativo)
    total_impressoras = Impressora.query.count()
    total_online = Impressora.query.filter_by(online=True).count()
    total_offline = Impressora.query.filter_by(online=False).count()

    pagination = ImpressorasService.listar_impressoras_paginadas(
        busca=busca,
        status_filtro=status_filtro,
        suprimento_filtro=suprimento_filtro,
        tipo_filtro=tipo_filtro,
        page=page
    )

    familias = SuprimentosService.listar_familias()

    from services.email_service import EmailService
    email_config = EmailService.get_smtp_config()
    impressoras_com_contagem = ImpressorasService.listar_impressoras_com_contagem()
    
    agora_hoje = datetime.now()
    default_assunto = f"[{email_config['mail_from_name']}] Relatório de Contagem de Páginas — {agora_hoje.strftime('%d/%m/%Y')}"
    default_mensagem = f"Olá equipe,\n\nSegue em anexo o relatório oficial consolidado com a contagem total de páginas do parque de impressoras, emitido em {agora_hoje.strftime('%d/%m/%Y às %H:%M')}.\n\nQualquer dúvida, estamos à disposição."

    return render_template(
        "impressoras/impressoras.html",
        impressoras=pagination.items,
        pagination=pagination,
        familias=familias,
        total_impressoras=total_impressoras,
        total_online=total_online,
        total_offline=total_offline,
        email_config=email_config,
        impressoras_com_contagem=impressoras_com_contagem,
        default_assunto=default_assunto,
        default_mensagem=default_mensagem,
        data_hoje=agora_hoje.strftime("%d/%m/%Y às %H:%M"),
        filtros={
            "busca": busca,
            "status": status_filtro,
            "suprimento": suprimento_filtro,
            "tipo": tipo_filtro
        }
    )

@impressoras_bp.route("/relatorio-paginas-pdf")
@login_required
@printer_staff_required
def relatorio_paginas_pdf():
    """Gera e faz o download direto do relatório de contagem de páginas em PDF."""
    buffer = ImpressorasService.gerar_pdf_contadores()
    nome_arquivo = f"relatorio_contagem_paginas_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nome_arquivo
    )

@impressoras_bp.route("/enviar-relatorio-email", methods=["POST"])
@login_required
@printer_staff_required
def enviar_relatorio_email():
    """Gera o relatório de contagem de páginas e envia por e-mail corporativo com o PDF anexado."""
    destinatarios = request.form.get("destinatarios", "").strip()
    assunto = request.form.get("assunto", "").strip()
    mensagem = request.form.get("mensagem", "").strip()
    incluir_tabela = request.form.get("incluir_tabela", "1") in ("1", "true", "on", "yes")
    
    if not destinatarios:
        flash("Informe ao menos um endereço de e-mail destinatário.", "warning")
        return redirect(url_for("impressoras.index"))

    impressoras_com_contagem = ImpressorasService.listar_impressoras_com_contagem()

    # Gera o PDF oficial em memória
    buffer = ImpressorasService.gerar_pdf_contadores()

    # Envia via serviço corporativo
    from services.email_service import EmailService
    sucesso, mensagem_retorno = EmailService.enviar_relatorio_impressoras(
        destinatarios=destinatarios,
        pdf_buffer=buffer,
        impressoras_com_contagem=impressoras_com_contagem,
        assunto=assunto,
        mensagem_texto=mensagem,
        incluir_tabela=incluir_tabela
    )

    if sucesso:
        flash(mensagem_retorno, "success")
    else:
        flash(mensagem_retorno, "danger")

    return redirect(url_for("impressoras.index"))
    
@impressoras_bp.route("/nova", methods=["GET", "POST"])
@login_required
@printer_staff_required
def nova_impressora():

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        ip = request.form.get("ip", "").strip()
        modelo = request.form.get("modelo", "").strip()
        serial = request.form.get("serial", "").strip()
        local = request.form.get("local", "").strip()
        contato = request.form.get("contato", "").strip()
        andar = request.form.get("andar", "").strip()
        sala = request.form.get("sala", "").strip()
        suprimento_id = request.form.get("suprimento_id")
        paginas_raw = request.form.get("paginas_impressas", "0")

        try:
            paginas = int(paginas_raw.replace('.', '').replace(',', '').strip()) if paginas_raw else 0
        except (ValueError, TypeError):
            paginas = 0

        try:
            suprimento_id_int = int(suprimento_id) if suprimento_id else None
        except (ValueError, TypeError):
            suprimento_id_int = None

        ImpressorasService.adicionar_impressora(
            nome=nome,
            ip=ip if ip else None,
            modelo=modelo if modelo else None,
            serial=serial if serial else None,
            local=local if local else None,
            contato=contato if contato else None,
            andar=andar if andar else "Não Informado",
            sala=sala if sala else "Não Informado",
            suprimento_id=suprimento_id_int,
            paginas_impressas=paginas,
            online=True
        )
        flash("Impressora adicionada com sucesso!", "success")
        return redirect(
            url_for("impressoras.index")
        )

    familias = SuprimentosService.listar_familias()
    return render_template(
        "impressoras/nova_impressora.html",
        familias=familias
    )

@impressoras_bp.route("/descobrir", methods=["GET", "POST"])
@login_required
@printer_staff_required
def descobrir_impressoras():
    ImpressorasService.descobrir_impressoras()
    flash("Varredura de descoberta finalizada.", "success")
    return redirect(
        url_for("impressoras.index")
    )
    
@impressoras_bp.route("/sincronizar", methods=["GET", "POST"])
@login_required
@printer_staff_required
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
@printer_staff_required
def atualizar_status():
    ImpressorasService.atualizar_status()
    flash("Status das impressoras atualizado!", "success")
    return redirect(
        url_for("impressoras.index")
    )
    
@impressoras_bp.route("/teste-web")
@login_required
@printer_staff_required
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
@printer_staff_required
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
@printer_staff_required
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
@printer_staff_required
def adicionar_estoque(familia_id):
    toner_add = request.form.get('toner_add', 0)
    cilindro_add = request.form.get('cilindro_add', 0)

    sucesso, mensagem = SuprimentosService.adicionar_estoque(familia_id, toner_add, cilindro_add)
    flash(mensagem, 'success' if sucesso else 'danger')
    return redirect(url_for('impressoras.gerenciar_estoque'))

@impressoras_bp.route('/retirar/<int:impressora_id>', methods=['POST'])
@login_required
@printer_staff_required
def retirar_insumo(impressora_id):
    tipo_insumo = request.form.get('tipo_insumo') # 'toner' ou 'cilindro'
    usuario_nome = current_user.nome if hasattr(current_user, 'nome') else 'Sistema'

    sucesso, mensagem = SuprimentosService.retirar_insumo(impressora_id, tipo_insumo, usuario_nome)
    flash(mensagem, 'success' if sucesso else 'danger')
    return redirect(url_for('impressoras.index'))

@impressoras_bp.route('/vincular/<int:impressora_id>', methods=['POST'])
@impressoras_bp.route('/editar/<int:impressora_id>', methods=['POST'])
@login_required
@printer_staff_required
def vincular_impressora(impressora_id):
    impressora = db.session.get(Impressora, impressora_id)
    if not impressora:
        flash("Impressora não encontrada.", "danger")
        return redirect(url_for('impressoras.index'))

    # Localização
    if 'andar' in request.form:
        impressora.andar = request.form.get('andar', impressora.andar)
    if 'sala' in request.form:
        impressora.sala = request.form.get('sala', impressora.sala)
    if 'local' in request.form:
        novo_local = request.form.get('local', '').strip()
        impressora.local = novo_local if novo_local else None

    # Contato e Serial
    if 'contato' in request.form:
        novo_contato = request.form.get('contato', '').strip()
        impressora.contato = novo_contato if novo_contato else None
    if 'serial' in request.form:
        novo_serial = request.form.get('serial', '').strip()
        impressora.serial = novo_serial if novo_serial else None

    # Nome e Modelo (se fornecidos)
    if 'nome' in request.form:
        novo_nome = request.form.get('nome', '').strip()
        if novo_nome:
            impressora.nome = novo_nome
    if 'modelo' in request.form:
        novo_modelo = request.form.get('modelo', '').strip()
        if novo_modelo:
            impressora.modelo = novo_modelo

    # Suprimento
    if 'suprimento_id' in request.form:
        suprimento_id = request.form.get('suprimento_id')
        try:
            impressora.suprimento_id = int(suprimento_id) if suprimento_id else None
        except (ValueError, TypeError):
            impressora.suprimento_id = None

    # Contador Manual de Páginas
    paginas_str = request.form.get('paginas_impressas')
    if paginas_str is not None and paginas_str.strip() != '':
        try:
            nova_qtd = int(paginas_str.replace('.', '').replace(',', '').strip())
            impressora.paginas_impressas = nova_qtd
            impressora.ultimo_check = datetime.now()
        except (ValueError, TypeError):
            pass

    # Status Operacional (Online / Ativa)
    if 'online' in request.form:
        impressora.online = request.form.get('online') in ('1', 'true', 'on', 'True')

    if impressora.ultimo_check is None:
        impressora.ultimo_check = datetime.now()

    db.session.commit()
    flash(f"Dados e contador da impressora {impressora.nome} atualizados com sucesso!", "success")
    return redirect(url_for('impressoras.index'))


@impressoras_bp.route('/estoque/ajustar/<int:familia_id>', methods=['POST'])
@login_required
@printer_staff_required
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