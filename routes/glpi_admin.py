"""
Rotas Administrativas Exclusivas do Administrador Supremo
Gerenciamento, Diagnostico e Auditoria da Integracao GLPI.
Acesso estritamente restrito via @supremo_required.
"""
import os
import time
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models import db, Chamado, GlpiSyncLog
from utils.decorator import supremo_required
from utils.glpi_client import GlpiClient
from services.glpi_sync import executar_sincronizacao
from utils.logger import get_logger

logger = get_logger('glpi_admin')

glpi_admin_bp = Blueprint('glpi_admin', __name__, url_prefix='/admin/glpi')

# Controle de rate limiting manual para impedir cliques seguidos no painel
_ultimo_disparo_manual = 0
INTERVALO_MINIMO_MANUAL = 30  # segundos


@glpi_admin_bp.route('/', methods=['GET'])
@login_required
@supremo_required
def painel():
    """Painel de Controle e Auditoria da API do GLPI (Exclusivo Supremo)."""
    # 1. Metricas gerais
    total_glpi = Chamado.query.filter_by(origem='glpi').count()
    hoje_inicio = datetime.combine(date.today(), datetime.min.time())
    hoje_glpi = Chamado.query.filter(
        Chamado.origem == 'glpi',
        Chamado.data_abertura >= hoje_inicio
    ).count()

    # 2. Status do Circuit Breaker
    agora = time.time()
    circuit_aberto = agora < GlpiClient._circuit_open_until
    tempo_restante_cooldown = max(0, int(GlpiClient._circuit_open_until - agora)) if circuit_aberto else 0

    # 3. Configuracoes mascaradas
    api_url = os.environ.get('GLPI_API_URL', 'https://helpdesk.brasfort.com.br/api.php')
    client_id_raw = os.environ.get('GLPI_CLIENT_ID', '')
    client_id_mascarado = f"{client_id_raw[:8]}...{client_id_raw[-6:]}" if len(client_id_raw) > 14 else "Configurado"
    intervalo_minutos = int(os.environ.get('GLPI_SYNC_INTERVAL_MINUTES', 15))
    batch_size = int(os.environ.get('GLPI_BATCH_SIZE', 15))
    sync_ativo = os.environ.get('GLPI_ENABLE_SYNC', 'false').lower() in ('true', '1')

    # 4. Historico recente de logs de sincronizacao
    logs = GlpiSyncLog.query.order_by(GlpiSyncLog.id.desc()).limit(20).all()

    return render_template(
        'glpi/painel_glpi.html',
        total_glpi=total_glpi,
        hoje_glpi=hoje_glpi,
        circuit_aberto=circuit_aberto,
        tempo_restante_cooldown=tempo_restante_cooldown,
        falhas_circuito=GlpiClient._circuit_failures,
        api_url=api_url,
        client_id_mascarado=client_id_mascarado,
        intervalo_minutos=intervalo_minutos,
        batch_size=batch_size,
        sync_ativo=sync_ativo,
        logs=logs
    )


@glpi_admin_bp.route('/sincronizar', methods=['POST'])
@login_required
@supremo_required
def sincronizar_manual():
    """Dispara a sincronizacao manual protegida contra sobrecarga e spam de cliques."""
    global _ultimo_disparo_manual
    agora = time.time()

    # Throttling manual: bloqueia se clicou ha menos de 30 segundos
    tempo_passado = agora - _ultimo_disparo_manual
    if tempo_passado < INTERVALO_MINIMO_MANUAL:
        espera = int(INTERVALO_MINIMO_MANUAL - tempo_passado)
        flash(f"Aguarde {espera}s antes de disparar uma nova sincronização manual para proteger o GLPI.", "warning")
        return redirect(url_for('glpi_admin.painel'))

    _ultimo_disparo_manual = agora
    logger.info(f"Sincronizacao manual solicitada pelo Administrador Supremo {current_user.email}.")

    resultado = executar_sincronizacao(dry_run=False)

    if resultado.get('status') == 'Sucesso':
        flash(
            f"Sincronização concluída! {resultado.get('novos_importados', 0)} novos chamados importados "
            f"de {resultado.get('total_encontrados', 0)} verificados.",
            "success"
        )
    elif resultado.get('status') == 'Ignorado':
        flash("Uma sincronização já está em processamento em segundo plano. Aguarde a conclusão.", "info")
    else:
        flash(f"Atenção na sincronização: {resultado.get('mensagem', 'Erro desconhecido')}", "danger")

    return redirect(url_for('glpi_admin.painel'))


@glpi_admin_bp.route('/resetar-circuito', methods=['POST'])
@login_required
@supremo_required
def resetar_circuito():
    """Permite ao Administrador Supremo destravar o Circuit Breaker manualmente."""
    GlpiClient._circuit_open_until = 0
    GlpiClient._circuit_failures = 0
    logger.warning(f"Circuit Breaker resetado manualmente pelo Administrador Supremo {current_user.email}.")
    flash("Circuit Breaker resetado com sucesso! Comunicação com o GLPI reestabelecida.", "info")
    return redirect(url_for('glpi_admin.painel'))
