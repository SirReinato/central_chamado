"""
Servico de Sincronizacao GLPI -> Hub Central - SirReinato Brasfort
Executa o processamento com foco em:
- Extracao inteligente de campos para Criacao de Usuario no AD DS (Active Directory)
- Destaque e prioridade alta para chamados de Onboarding / Admissao
- Idempotencia absoluta (glpi_id unico)
- Registro de auditoria em GlpiSyncLog
- Execucao controlada e segura sob a Politica de Carga Zero
"""
import os
import re
import html
import threading
from datetime import datetime
from models import db, Chamado, GlpiSyncLog, Usuario
from utils.glpi_client import GlpiClient
from services.email_service import EmailService
from utils.logger import get_logger

logger = get_logger('glpi_sync')

# Lock de execucao para impedir sincronizacoes concorrentes
_sync_lock = threading.Lock()

MAPA_PRIORIDADE = {
    1: 'Baixa',
    2: 'Baixa',
    3: 'Média',
    4: 'Alta',
    5: 'Alta',
    6: 'Urgente'
}


def _limpar_html(conteudo_html: str) -> str:
    """Converte HTML retornado pelo GLPI em texto limpo, organizado e perfeitamente legivel."""
    if not conteudo_html:
        return ""
    # Decodifica entidades HTML (&nbsp;, &quot;, &amp;, etc.)
    texto = html.unescape(conteudo_html)
    # Substitui espacos nao-quebraveis por espacos normais
    texto = texto.replace('\xa0', ' ')
    # Trata quebras de bloco e paragrafos antes de remover tags
    texto = re.sub(r'</?(?:div|p|h[1-6]|li|tr)[^>]*>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'<br\s*/?>', '\n', texto, flags=re.IGNORECASE)
    # Remove qualquer outra tag HTML
    texto = re.sub(r'<[^>]+>', '', texto)
    # Normaliza quebras de linha multiplas para no maximo duas
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    # Remove espacos em branco nas extremidades de cada linha
    linhas = [linha.strip() for linha in texto.splitlines()]
    return '\n'.join(linhas).strip()


def _extrair_campos_formulario(conteudo_html: str) -> dict:
    """
    Extrai campos rotulados no padrao de formularios do GLPI (ex: <b>X) Campo</b>: Valor ou <strong>).
    Suporta quebras de linha (<br>, <p>), colons internos e campos multilinhas.
    """
    if not conteudo_html:
        return {}
    txt = html.unescape(conteudo_html).replace('\xa0', ' ')
    txt = re.sub(r'</?(?:p|div|br)[^>]*>', '\n', txt, flags=re.IGNORECASE)

    # Padrao que encontra rotulos delimitados por <b> ou <strong>
    padrao = r'<(?:b|strong)>\s*(\d+\)\s*[^<]+?)\s*</(?:b|strong)>\s*:?'
    partes = re.split(padrao, txt, flags=re.IGNORECASE)

    campos = {}
    if len(partes) > 1:
        for i in range(1, len(partes), 2):
            rotulo_bruto = partes[i].strip()
            rotulo = re.sub(r'^\d+\)\s*', '', rotulo_bruto).rstrip(':').strip()
            valor_bruto = partes[i+1] if i+1 < len(partes) else ''
            valor_limpo = re.sub(r'<[^>]+>', '', valor_bruto)
            linhas = [l.strip() for l in valor_limpo.splitlines() if l.strip() and l.strip() != ':']
            valor_final = ' '.join(linhas).strip()
            if rotulo and valor_final:
                campos[rotulo] = valor_final

    # Fallback para formato legado caso nada seja capturado
    if not campos:
        padrao_legado = r'<(?:b|strong)>\s*(?:(\d+\)\s*)?([^<:]+)\s*</(?:b|strong)>\s*:\s*([^<\n\r]+)'
        matches = re.findall(padrao_legado, txt, flags=re.IGNORECASE)
        for _, k, v in matches:
            k_clean = k.strip()
            v_clean = re.sub(r'<[^>]+>', '', v).strip()
            if v_clean:
                campos[k_clean] = v_clean

    return campos


def _extrair_solicitante(ticket: dict) -> str:
    """Extrai o nome legivel do solicitante da equipe ou objeto de usuario."""
    team = ticket.get('team') or []
    for membro in team:
        if membro.get('role') == 'requester':
            display = membro.get('display_name') or f"{membro.get('firstname', '')} {membro.get('realname', '')}".strip()
            if display:
                return display
            if membro.get('name'):
                return membro.get('name')

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
        data_limpa = data_str[:19]
        return datetime.strptime(data_limpa, "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return datetime.now()


def _formatar_dados_ad_ds(campos: dict, t_id: int, descricao_original: str) -> tuple:
    """
    Identifica se e um formulario de Criacao de Usuario e gera um resumo
    estruturado com os dados essenciais para criacao da conta no AD DS.
    Retorna: (is_user_form, titulo_formatado, solicitante_formatado, setor_formatado, categoria, prioridade, descricao_final)
    """
    # Detecta se e formulario de criacao de usuario
    chaves_usuario = [k for k in campos.keys() if 'colaborador' in k.lower() or 'admiss' in k.lower()]
    is_user_form = len(chaves_usuario) > 0 or 'criação de usuário' in descricao_original.lower() or 'criacao de usuario' in descricao_original.lower()

    if not is_user_form:
        return False, None, None, None, None, None, descricao_original

    # 1. Extracao dos campos para o AD
    nome = campos.get('Nome do Colaborador') or campos.get('Colaborador') or 'Novo Colaborador'
    logon = campos.get('E-mail corporativo') or campos.get('Email corporativo') or ''
    logon_limpo = re.sub(r'[^a-zA-Z0-9._-]', '', logon.split('@')[0].lower()) if logon else ''
    email_sugerido = f"{logon_limpo}@brasfort.com.br" if logon_limpo else 'Não informado'

    setor = campos.get('Setor') or campos.get('Setor / Posto / Contrato') or 'TI / Operações'
    empresa = campos.get('Empresa') or campos.get('Empresa / Unidade de negócio') or 'Brasfort'
    funcao = campos.get('Função') or campos.get('Funcao') or campos.get('Funo') or campos.get('Cargo') or 'Não informado'
    lider = campos.get('Líder direto') or campos.get('Lder direto') or campos.get('Gestor responsável') or 'Não informado'
    admissao = campos.get('Admissão') or campos.get('Admisso') or campos.get('Prazo necessário') or 'Não informado'
    recursos = campos.get('Acessos necessários') or campos.get('Acessos necessrios') or 'E-mail corporativo, Computador'
    registro = campos.get('Registro') or campos.get('Matrícula') or '-'
    cpf = campos.get('CPF') or '-'
    rg = campos.get('RG') or '-'
    telefone = campos.get('E-mail / Telefone') or campos.get('Telefone') or '-'

    # 2. Titulo e Solicitante amigaveis
    titulo_formatado = f"Criação de Usuário: {nome} ({empresa})"
    solicitante_formatado = nome
    setor_formatado = setor
    categoria = "Criação de Usuário"
    prioridade = "Alta"  # Alta prioridade para onboarding

    # 3. Montagem da descricao limpa e estruturada para AD DS
    descricao_ad = f"""======================================================================
📋 DADOS ESSENCIAIS PARA CRIAÇÃO NO ACTIVE DIRECTORY (AD DS)
======================================================================
• Nome Completo (Display Name) : {nome}
• Logon Sugerido (SamAccount)  : {logon_limpo or 'definir.padrao'}
• E-mail Corporativo Sugerido  : {email_sugerido}
• Setor / Departamento (OU)    : {setor}
• Empresa / Unidade de Negócio : {empresa}
• Cargo / Função (Title)       : {funcao}
• Gestor / Líder Direto        : {lider}
• Data de Admissão             : {admissao}
• Recursos & Acessos           : {recursos}
• Registro / Matrícula         : {registro}
• Documentos                   : CPF: {cpf} | RG: {rg}
• Telefone / Contato           : {telefone}
======================================================================

📄 DETALHES DO FORMULÁRIO COMPLETO (GLPI #{t_id}):
{descricao_original}"""

    return True, titulo_formatado, solicitante_formatado, setor_formatado, categoria, prioridade, descricao_ad


def _formatar_dados_cancelamento_nf(
    campos: dict,
    t_id: int,
    descricao_original: str,
    base_glpi_url: str,
    solicitante_original: str = ""
) -> tuple:
    """
    Identifica se e um formulario de Cancelamento de Nota Fiscal (ID 36) e gera
    a formatacao estruturada para auditoria e o link de aprovacao no GLPI.
    Retorna: (is_nf_form, titulo_formatado, solicitante_formatado, categoria, prioridade, descricao_final, link_glpi)
    """
    chaves_nf = [k for k in campos.keys() if 'nfe' in k.lower() or 'nota fiscal' in k.lower()]
    is_nf_form = len(chaves_nf) > 0 or 'cancelamento de nota fiscal' in descricao_original.lower()

    if not is_nf_form:
        return False, None, None, None, None, descricao_original, None

    numero_nf = campos.get('NFe nº / Série') or campos.get('NFe nº / Serie') or campos.get('NFe') or '-'
    valor = campos.get('Valor') or '-'
    cliente = campos.get('Cliente / Contrato') or campos.get('Cliente') or 'Cliente não informado'
    data_emissao = campos.get('Data de emissão') or campos.get('Data de emissao') or '-'
    motivo = campos.get('Motivo do pedido') or '-'
    evidencias = campos.get('Evidências') or campos.get('Evidencias') or '-'
    categoria_causa = campos.get('Categoria da causa  (pré-análise)') or campos.get('Categoria da causa') or '-'
    risco = campos.get('Risco se não cancelar') or '-'
    acao = campos.get('Ação corretiva/evitativa proposta') or '-'
    responsavel = campos.get('Responsável pelo ajuste / Prazo') or '-'

    link_glpi = f"{base_glpi_url.rstrip('/')}/front/ticket.form.php?id={t_id}"

    titulo_formatado = f"Cancelamento NF #{numero_nf}: {cliente} (R$ {valor})"
    solicitante_formatado = f"{solicitante_original} (NF #{numero_nf})"
    categoria = "Cancelamento de Nota Fiscal"
    prioridade = "Alta"

    descricao_nf = f"""======================================================================
📑 SOLICITAÇÃO DE CANCELAMENTO DE NOTA FISCAL (GLPI #{t_id})
======================================================================
• NFe nº / Série          : {numero_nf}
• Valor da Nota           : R$ {valor}
• Data de Emissão         : {data_emissao}
• Cliente / Contrato      : {cliente}
• Solicitante             : {solicitante_original}
• Categoria da Causa      : {categoria_causa}
• Motivo do Pedido        : {motivo}
• Evidências              : {evidencias}
• Risco se não cancelar   : {risco}
• Ação Corretiva Proposta : {acao}
• Responsável / Prazo     : {responsavel}
======================================================================
🔗 LINK DIRETO PARA AVALIAÇÃO / APROVAÇÃO NO GLPI:
{link_glpi}
======================================================================

📄 DETALHES COMPLETOS DO FORMULÁRIO (GLPI #{t_id}):
{descricao_original}"""

    return True, titulo_formatado, solicitante_formatado, categoria, prioridade, descricao_nf, link_glpi


def executar_sincronizacao(dry_run: bool = False) -> dict:
    """
    Executa a sincronizacao com o GLPI.
    Garante execucao unica atraves de threading.Lock.
    Filtra estritamente chamados ABERTOS (Novo ou com tecnico atribuido especificado).
    """
    if not _sync_lock.acquire(blocking=False):
        logger.warning("Sincronizacao GLPI ja em andamento. Execucao ignorada para evitar concorrencia.")
        return {'status': 'Ignorado', 'motivo': 'Execucao em andamento'}

    resultado = {
        'total_encontrados': 0,
        'elegiveis_formulario': 0,
        'novos_importados': 0,
        'ja_existentes': 0,
        'fechados_conciliados': 0,
        'emails_enviados': 0,
        'dry_run': dry_run,
        'status': 'Sucesso',
        'mensagem': ''
    }

    try:
        client = GlpiClient()

        # Determina o usuario local padrao para vincular chamados importados
        usuario_padrao = Usuario.query.filter_by(perfil='admin').first() or Usuario.query.first()
        usuario_id_padrao = usuario_padrao.id if usuario_padrao else 1

        # Configuracoes de Filtros Avancados
        filtro_apenas_abertos = os.environ.get('GLPI_FILTER_ONLY_OPEN', 'true').lower() in ('true', '1')
        tecnico_alvo = os.environ.get('GLPI_TECH_USERNAME', os.environ.get('GLPI_USERNAME', 'renato.lima')).strip().lower()
        filtro_tipo = os.environ.get('GLPI_FILTER_REQUEST_TYPE_ID', '1').strip()
        filtro_cat = os.environ.get('GLPI_FILTER_CATEGORY_ID', '').strip()
        filtro_apenas_form = os.environ.get('GLPI_FILTER_ONLY_FORMS', 'false').lower() in ('true', '1')

        # Obter o maior glpi_id ja registrado no banco local (avalia Chamados e logs de sincronizacao)
        ultimo_chamado = Chamado.query.filter(Chamado.glpi_id.isnot(None)).order_by(Chamado.glpi_id.desc()).first()
        ultimo_chamado_id = ultimo_chamado.glpi_id if ultimo_chamado else None

        ultimo_log = GlpiSyncLog.query.filter(
            GlpiSyncLog.status == 'Sucesso',
            GlpiSyncLog.ultimo_ticket_id.isnot(None)
        ).order_by(GlpiSyncLog.id.desc()).first()
        ultimo_log_id = ultimo_log.ultimo_ticket_id if ultimo_log else None

        ultimo_id = max(filter(None, [ultimo_chamado_id, ultimo_log_id]), default=None)

        logger.info(
            f"Iniciando varredura GLPI. Apenas abertos: {filtro_apenas_abertos} | "
            f"Tecnico alvo: '{tecnico_alvo}' | Ultimo ID: #{ultimo_id or 0} | Dry-run: {dry_run}"
        )

        if filtro_apenas_abertos:
            # Consulta todos os tickets atualmente abertos no GLPI (status 1, 2, 3, 4) em 1 unica chamada leve
            tickets_brutos = client.buscar_tickets_abertos(limite=100)
        else:
            tickets_brutos = client.buscar_tickets(ultimo_glpi_id=ultimo_id)

        resultado['total_encontrados'] = len(tickets_brutos)
        maior_id_processado = ultimo_id or 0

        # Mapeia IDs abertos no GLPI para conciliacao
        ids_abertos_glpi = set()

        for t in tickets_brutos:
            t_id = t.get('id')
            if not t_id:
                continue

            ids_abertos_glpi.add(t_id)

            if t_id > maior_id_processado:
                maior_id_processado = t_id

            # Filtro 1: Status Aberto (GLPI: 1=Novo, 2=Em atendimento, 3=Planejado, 4=Pendente)
            st = t.get('status') or {}
            st_id = st.get('id') if isinstance(st, dict) else st
            if filtro_apenas_abertos and st_id not in (1, 2, 3, 4):
                logger.debug(f"Ticket #{t_id} ignorado por status fechado/resolvido ({st_id}).")
                continue

            # Filtro 2: Atribuicao -> Deve ser 'Novo' (sem tecnico / status 1) OU estar atribuido ao tecnico_alvo
            tecnicos_atribuidos = [
                m.get('name', '').lower()
                for m in (t.get('team') or [])
                if m.get('role') == 'assigned' and m.get('name')
            ]
            is_novo = (st_id == 1)
            is_atribuido_alvo = bool(tecnico_alvo and tecnico_alvo in tecnicos_atribuidos)

            if filtro_apenas_abertos and not (is_novo or is_atribuido_alvo):
                logger.debug(
                    f"Ticket #{t_id} ignorado: nao e 'Novo' nem atribuido a {tecnico_alvo} "
                    f"(Status: {st_id}, Tecnicos: {tecnicos_atribuidos})."
                )
                continue

            # Filtro 3: Tipo de requisicao (opcional, ex: Helpdesk / 1)
            req_type = t.get('request_type') or {}
            req_type_id = str(req_type.get('id', ''))
            if filtro_tipo and req_type_id != filtro_tipo:
                logger.debug(f"Ticket #{t_id} ignorado por origem: {req_type.get('name')} (id={req_type_id} != {filtro_tipo})")
                continue

            # Filtro 4: Categoria (opcional)
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

            # Mapeamento basico
            titulo = t.get('name', f"Chamado GLPI #{t_id}").strip()
            descricao_bruta = t.get('content', '')
            descricao_limpa = _limpar_html(descricao_bruta) or "Chamado importado do GLPI sem descricao textual."
            
            solicitante_original = _extrair_solicitante(t)
            setor_original = _extrair_setor(t)
            categoria_nome = cat.get('name') or "Outros"
            
            prio_num = t.get('priority', 3)
            prioridade = MAPA_PRIORIDADE.get(prio_num, 'Média')

            # Base URL da interface web do GLPI
            base_glpi_url = re.sub(r'/api\.php.*$', '', client.api_url)

            # Parser inteligente para formularios
            campos_form = _extrair_campos_formulario(descricao_bruta)

            # 1. Formulario de Criacao de Usuario / AD DS
            is_user_form, tit_fmt, sol_fmt, set_fmt, cat_fmt, prio_fmt, desc_final = _formatar_dados_ad_ds(
                campos=campos_form,
                t_id=t_id,
                descricao_original=descricao_limpa
            )

            # 2. Formulario de Cancelamento de Nota Fiscal (ID 36)
            is_nf_form, tit_nf, sol_nf, cat_nf, prio_nf, desc_nf, link_nf = _formatar_dados_cancelamento_nf(
                campos=campos_form,
                t_id=t_id,
                descricao_original=descricao_limpa,
                base_glpi_url=base_glpi_url,
                solicitante_original=solicitante_original
            )

            # Filtro 5: Opcional - restringe apenas a chamados originados de formularios
            if filtro_apenas_form and not (is_user_form or is_nf_form) and len(campos_form) == 0:
                logger.debug(f"Ticket #{t_id} ignorado pois nao e um formulario (GLPI_FILTER_ONLY_FORMS ativo).")
                continue

            if is_user_form:
                titulo = tit_fmt or titulo
                solicitante = f"{sol_fmt} (Solicitado por: {solicitante_original})"
                setor = set_fmt or setor_original
                categoria_nome = cat_fmt or categoria_nome
                prioridade = prio_fmt or prioridade
                descricao = desc_final
            elif is_nf_form:
                titulo = tit_nf or titulo
                solicitante = sol_nf or solicitante_original
                setor = "Financeiro / Faturamento"
                categoria_nome = cat_nf or "Cancelamento de Nota Fiscal"
                prioridade = prio_nf or "Alta"
                descricao = desc_nf
            else:
                solicitante = solicitante_original
                setor = setor_original
                descricao = descricao_limpa

            # Status: Todo novo chamado aberto importado do GLPI entra como 'Aberto' para ser atendido na Central
            status_local = 'Aberto'
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

                # Disparo de alerta por e-mail para aprovacao de Cancelamento de NF
                if is_nf_form:
                    try:
                        logger.info(f"Disparando e-mail de alerta para Cancelamento de NF #{t_id}...")
                        sucesso_mail, msg_mail = EmailService.enviar_notificacao_cancelamento_nf(
                            chamado_glpi_id=t_id,
                            dados_nf=campos_form,
                            solicitante=solicitante_original,
                            link_glpi=link_nf
                        )
                        if sucesso_mail:
                            resultado['emails_enviados'] += 1
                            logger.info(f"E-mail de aprovacao para NF #{t_id} enviado com sucesso!")
                        else:
                            logger.warning(f"Falha ao enviar e-mail de aprovacao para NF #{t_id}: {msg_mail}")
                    except Exception as err_mail:
                        logger.error(f"Erro no envio de e-mail de aprovacao para NF #{t_id}: {err_mail}", exc_info=True)

            resultado['novos_importados'] += 1

        # Conciliacao automatica de chamados fechados no GLPI
        if filtro_apenas_abertos and not dry_run:
            chamados_locais_abertos = Chamado.query.filter(
                Chamado.origem == 'glpi',
                Chamado.status.in_(['Aberto', 'Em Atendimento', 'Pendente'])
            ).all()

            for ch in chamados_locais_abertos:
                if ch.glpi_id and ch.glpi_id not in ids_abertos_glpi:
                    logger.info(f"Chamado local #{ch.id} (GLPI #{ch.glpi_id}) nao esta mais aberto no GLPI. Atualizando para 'Resolvido'.")
                    ch.status = 'Resolvido'
                    ch.data_fechamento = datetime.now()
                    resultado['fechados_conciliados'] += 1

        if not dry_run:
            db.session.commit()

            msg_part_email = f" {resultado['emails_enviados']} e-mails de alerta enviados." if resultado['emails_enviados'] > 0 else ""
            log_sync = GlpiSyncLog(
                data_execucao=datetime.now(),
                tickets_encontrados=resultado['total_encontrados'],
                tickets_importados=resultado['novos_importados'],
                status='Sucesso',
                mensagem=(
                    f"Verificados {resultado['total_encontrados']} tickets abertos. "
                    f"{resultado['novos_importados']} importados (Novo ou {tecnico_alvo}). "
                    f"{resultado['fechados_conciliados']} conciliados para Resolvido."
                    f"{msg_part_email}"
                ),
                ultimo_ticket_id=maior_id_processado if maior_id_processado > 0 else ultimo_id
            )
            db.session.add(log_sync)
            db.session.commit()

        resultado['mensagem'] = (
            f"Concluido com sucesso. {resultado['novos_importados']} novos importados de "
            f"{resultado['total_encontrados']} abertos analisados. "
            f"{resultado['fechados_conciliados']} conciliados para Resolvido. "
            f"{resultado['emails_enviados']} e-mails enviados."
        )
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
