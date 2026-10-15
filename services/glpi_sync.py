"""
Servico de Sincronizacao GLPI -> Central de Chamados
Executa o processamento sob demanda ou via scheduler de forma:
- Segura e Idempotente (nao duplica chamados)
- Filtrada exclusivamente para chamados de Formulario (request_type.id == 1)
- Com registro de auditoria em GlpiSyncLog
- Com suporte a simulacao (dry_run)
"""
import os
import re
import html
import threading
from datetime import datetime
from models import db, Chamado, GlpiSyncLog, Usuario
from utils.glpi_client import GlpiClient
from utils.logger import get_logger

logger = get_logger('glpi_sync')

# Lock de execucao para impedir sincronizacoes concorrentes
_sync_lock = threading.Lock()

# Mapeamento de prioridades numericas do GLPI para texto local
MAPA_PRIORIDADE = {
    1: 'Baixa',
    2: 'Baixa',
    3: 'Média',
    4: 'Alta',
    5: 'Alta',
    6: 'Urgente'
}

# Mapeamento de status do GLPI para o fluxo da Central
MAPA_STATUS = {
    1: 'Aberto',          # Novo
    2: 'Em Atendimento',  # Em processamento (atribuido)
    3: 'Em Atendimento',  # Em processamento (planejado)
    4: 'Pendente',        # Pendente
    5: 'Resolvido',       # Solucionado
    6: 'Fechado'          # Fechado
}


def _limpar_html(conteudo_html: str) -> str:
    """Converte HTML simples retornado pelo GLPI em texto limpo e legivel."""
    if not conteudo_html:
        return ""
    texto = html.unescape(conteudo_html)
    # Substitui quebras de linha HTML
    texto = re.sub(r'<br\s*/?>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'</p>', '\n', texto, flags=re.IGNORECASE)
    # Remove qualquer outra tag HTML
    texto = re.sub(r'<[^>]+>', '', texto)
    return texto.strip()


def _extrair_solicitante(ticket: dict) -> str:
    """Extrai o nome legivel do solicitante da equipe ou objeto de usuario."""
    # 1. Procura na lista de team por role == 'requester'
    team = ticket.get('team') or []
    for membro in team:
        if membro.get('role') == 'requester':
            display = membro.get('display_name') or f"{membro.get('firstname', '')} {membro.get('realname', '')}".strip()
            if display:
                return display
            if membro.get('name'):
                return membro.get('name')

    # 2. Tenta user_recipient
    user_rec = ticket.get('user_recipient')
    if isinstance(user_rec, dict) and user_rec.get('name'):
        return user_rec.get('name')

    return "Solicitante GLPI"


def _extrair_setor(ticket: dict) -> str:
    """Extrai a localizacao/setor do chamado."""
    location = ticket.get('location')
    if isinstance(location, dict) and location.get('name'):
        return location.get('name')
    return "Geral / GLPI"


def _converter_data(data_str: str) -> datetime:
    """Converte string ISO de data do GLPI para datetime do Python."""
    if not data_str:
        return datetime.now()
    try:
        # Trata formato ISO ex: 2026-08-31T11:31:20-03:00
        data_limpa = data_str[:19]
        return datetime.strptime(data_limpa, "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return datetime.now()


def executar_sincronizacao(dry_run: bool = False) -> dict:
    """
    Executa a sincronizacao com o GLPI.
    Garante execucao unica atraves de threading.Lock.
    """
    if not _sync_lock.acquire(blocking=False):
        logger.warning("Sincronizacao GLPI ja em andamento. Execucao ignorada para evitar concorrencia.")
        return {'status': 'Ignorado', 'motivo': 'Execucao em andamento'}

    resultado = {
        'total_encontrados': 0,
        'elegiveis_formulario': 0,
        'novos_importados': 0,
        'ja_existentes': 0,
        'dry_run': dry_run,
        'status': 'Sucesso',
        'mensagem': ''
    }

    try:
        client = GlpiClient()

        # Determina o usuario local padrao para vincular chamados importados
        usuario_padrao = Usuario.query.filter_by(perfil='admin').first() or Usuario.query.first()
        usuario_id_padrao = usuario_padrao.id if usuario_padrao else 1

        # Obter o maior glpi_id ja registrado no banco local
        ultimo_chamado = Chamado.query.filter(Chamado.glpi_id.isnot(None)).order_by(Chamado.glpi_id.desc()).first()
        ultimo_id = ultimo_chamado.glpi_id if ultimo_chamado else None

        logger.info(f"Iniciando varredura GLPI. Ultimo GLPI ID registrado: #{ultimo_id or 0}. Dry-run: {dry_run}")

        tickets_brutos = client.buscar_tickets(ultimo_glpi_id=ultimo_id)
        resultado['total_encontrados'] = len(tickets_brutos)

        filtro_tipo = os.environ.get('GLPI_FILTER_REQUEST_TYPE_ID', '1').strip()
        filtro_cat = os.environ.get('GLPI_FILTER_CATEGORY_ID', '').strip()

        maior_id_processado = ultimo_id or 0

        for t in tickets_brutos:
            t_id = t.get('id')
            if not t_id:
                continue

            if t_id > maior_id_processado:
                maior_id_processado = t_id

            # Filtro 1: Apenas chamados de Formulario (ex: request_type.id == 1 / Helpdesk)
            req_type = t.get('request_type') or {}
            req_type_id = str(req_type.get('id', ''))
            
            if filtro_tipo and req_type_id != filtro_tipo:
                logger.debug(f"Ticket #{t_id} ignorado por origem: {req_type.get('name')} (id={req_type_id} != {filtro_tipo})")
                continue

            # Filtro 2: Categoria (opcional)
            cat = t.get('category') or {}
            cat_id = str(cat.get('id', ''))
            if filtro_cat and cat_id != filtro_cat:
                logger.debug(f"Ticket #{t_id} ignorado por categoria id={cat_id}")
                continue

            resultado['elegiveis_formulario'] += 1

            # Idempotencia: Verificar se ja existe no banco
            chamado_existente = Chamado.query.filter_by(glpi_id=t_id).first()
            if chamado_existente:
                resultado['ja_existentes'] += 1
                continue

            # Mapeamento de dados
            titulo = t.get('name', f"Chamado GLPI #{t_id}").strip()
            descricao_bruta = t.get('content', '')
            descricao = _limpar_html(descricao_bruta) or "Chamado importado do GLPI sem descricao textual."
            
            solicitante = _extrair_solicitante(t)
            setor = _extrair_setor(t)
            
            # Categoria
            categoria_nome = cat.get('name') or "Outros"
            
            # Prioridade
            prio_num = t.get('priority', 3)
            prioridade = MAPA_PRIORIDADE.get(prio_num, 'Média')

            # Status
            st_obj = t.get('status') or {}
            st_id = st_obj.get('id', 1) if isinstance(st_obj, dict) else 1
            status_local = MAPA_STATUS.get(st_id, 'Aberto')

            data_abertura = _converter_data(t.get('date_creation'))

            if not dry_run:
                novo_chamado = Chamado(
                    usuario_id=usuario_id_padrao,
                    solicitante=solicitante[:100],
                    setor=setor[:100],
                    titulo=titulo[:200],
                    descricao=descricao,
                    categoria=categoria_nome[:50],
                    prioridade=prioridade,
                    status=status_local,
                    data_abertura=data_abertura,
                    origem='glpi',
                    glpi_id=t_id,
                    glpi_numero=str(t_id)
                )
                db.session.add(novo_chamado)

            resultado['novos_importados'] += 1

        if not dry_run:
            db.session.commit()

            # Grava registro no log de sincronizacao
            log_sync = GlpiSyncLog(
                data_execucao=datetime.now(),
                tickets_encontrados=resultado['total_encontrados'],
                tickets_importados=resultado['novos_importados'],
                status='Sucesso',
                mensagem=f"Processados {resultado['total_encontrados']} tickets. {resultado['novos_importados']} importados via formulario.",
                ultimo_ticket_id=maior_id_processado if maior_id_processado > 0 else ultimo_id
            )
            db.session.add(log_sync)
            db.session.commit()

        resultado['mensagem'] = f"Concluido com sucesso. {resultado['novos_importados']} importados de {resultado['total_encontrados']} analisados."
        logger.info(f"Sincronizacao GLPI finalizada: {resultado}")
        return resultado

    except Exception as e:
        if not dry_run:
            db.session.rollback()
            try:
                log_erro = GlpiSyncLog(
                    data_execucao=datetime.now(),
                    tickets_encontrados=resultado['total_encontrados'],
                    tickets_importados=0,
                    status='Erro',
                    mensagem=str(e)[:500]
                )
                db.session.add(log_erro)
                db.session.commit()
            except Exception:
                pass

        logger.error(f"Erro durante sincronizacao GLPI: {e}", exc_info=True)
        resultado['status'] = 'Erro'
        resultado['mensagem'] = str(e)
        return resultado

    finally:
        _sync_lock.release()
