from models import Impressora, db, EstoqueSuprimento
from utils.logger import get_logger

logger = get_logger('impressoras_services')

import io
import subprocess
import json
import re
import requests

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from pysnmp.hlapi import *

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from services.snmp_service import consultar_impressora, consultar_impressoras_bulk

class NumberedCanvas(canvas.Canvas):
    """Canvas customizado do ReportLab para numeração dinâmica de páginas (Página X de Y)."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(841.89 - 30, 18, page_text)
        self.drawString(30, 18, "Central de Chamados — Relatório de Monitoramento e Contadores de Impressão")
        self.restoreState()

class DualPagePagination:
    """
    Paginação dividida em exatamente 2 páginas temáticas:
    - Página 1: Impressoras Online
    - Página 2: Impressoras Offline / Controle Manual
    """
    def __init__(self, items, page, total_online, total_offline, status_nome):
        self.items = items
        self.page = page  # 1 ou 2
        self.pages = 2
        self.total = total_online + total_offline
        self.total_online = total_online
        self.total_offline = total_offline
        self.status_nome = status_nome  # "Online" ou "Offline"
        self.has_prev = (page > 1)
        self.has_next = (page < 2)
        self.prev_num = 1 if page > 1 else None
        self.next_num = 2 if page < 2 else None

    def iter_pages(self, left_edge=1, right_edge=1, left_current=2, right_current=2):
        return [1, 2]

class ImpressorasService:

    TERMOS_VIRTUAIS = (
        'pdf24',
        'generic',
        'text only',
        'print to pdf',
        'xps',
        'fax',
        'onenote',
        'anydesk',
        'adobe pdf'
    )

    @staticmethod
    def listar_impressoras():
        return Impressora.query.order_by(Impressora.online.desc(), Impressora.nome.asc()).all()

    @staticmethod
    def listar_impressoras_paginadas(busca=None, status_filtro=None, suprimento_filtro=None, tipo_filtro=None, page=1, per_page=None):
        """
        Retorna as impressoras divididas exclusivamente em 2 páginas:
        - Página 1: Todas as impressoras Online
        - Página 2: Todas as impressoras Offline (incluindo manuais)
        Mantém compatibilidade com todos os filtros (busca, suprimento, tipo).
        """
        query_base = Impressora.query

        if busca:
            termo = f"%{busca.strip()}%"
            query_base = query_base.filter(
                db.or_(
                    Impressora.nome.ilike(termo),
                    Impressora.ip.ilike(termo),
                    Impressora.serial.ilike(termo),
                    Impressora.modelo.ilike(termo),
                    Impressora.andar.ilike(termo),
                    Impressora.sala.ilike(termo),
                    Impressora.local.ilike(termo)
                )
            )

        if suprimento_filtro == 'vinculado':
            query_base = query_base.filter(Impressora.suprimento_id.isnot(None))
        elif suprimento_filtro == 'sem_vinculo':
            query_base = query_base.filter(Impressora.suprimento_id.is_(None))

        # Filtro de tipo: Apenas Físicas ou Apenas Virtuais
        if tipo_filtro == 'fisicas':
            for t in ImpressorasService.TERMOS_VIRTUAIS:
                query_base = query_base.filter(~Impressora.nome.ilike(f"%{t}%"))
        elif tipo_filtro == 'virtuais':
            condicoes = [Impressora.nome.ilike(f"%{t}%") for t in ImpressorasService.TERMOS_VIRTUAIS]
            query_base = query_base.filter(db.or_(*condicoes))

        # Contagens para cada status com base nos filtros ativos
        total_online = query_base.filter(Impressora.online.is_(True)).count()
        total_offline = query_base.filter(Impressora.online.is_(False)).count()

        # Determina a página: Página 1 = Online, Página 2 = Offline
        if status_filtro == 'offline' or page == 2:
            page_atual = 2
            status_nome = "Offline"
            query_pagina = query_base.filter(Impressora.online.is_(False)).order_by(Impressora.nome.asc())
        else:
            page_atual = 1
            status_nome = "Online"
            query_pagina = query_base.filter(Impressora.online.is_(True)).order_by(Impressora.nome.asc())

        items = query_pagina.all()

        return DualPagePagination(
            items=items,
            page=page_atual,
            total_online=total_online,
            total_offline=total_offline,
            status_nome=status_nome
        )



    @staticmethod
    def adicionar_impressora(
        nome,
        ip=None,
        modelo=None,
        serial=None,
        local=None,
        contato=None,
        andar=None,
        sala=None,
        suprimento_id=None,
        paginas_impressas=0,
        online=True
    ):
        ip_limpo = ip.strip() if ip and ip.strip() else None

        if ip_limpo:
            existente = Impressora.query.filter_by(ip=ip_limpo).first()
            if existente:
                return existente

        if serial and serial.strip():
            existente_serial = Impressora.query.filter_by(serial=serial.strip()).first()
            if existente_serial:
                return existente_serial

        impressora = Impressora(
            nome=nome.strip() if nome else "Nova Impressora",
            ip=ip_limpo,
            modelo=modelo.strip() if modelo else None,
            serial=serial.strip() if serial else None,
            local=local.strip() if local else None,
            contato=contato.strip() if contato else None,
            andar=andar.strip() if andar else "Não Informado",
            sala=sala.strip() if sala else "Não Informado",
            suprimento_id=suprimento_id,
            paginas_impressas=paginas_impressas or 0,
            online=online,
            ultimo_check=datetime.now()
        )

        db.session.add(impressora)
        db.session.commit()

        return impressora



    @staticmethod
    def _consultar_snmp(ip, oid, comunidade='public', porta=161, timeout=1):
        """Realiza uma consulta SNMP GET utilizando PySNMP de forma segura e com timeout curto."""
        try:
            errorIndication, errorStatus, errorIndex, varBinds = next(
                getCmd(
                    SnmpEngine(),
                    CommunityData(comunidade, mpModel=0), # SNMP v2c (mpModel=0 é v1, mpModel=1 é v2c)
                    UdpTransportTarget((ip, porta), timeout=timeout, retries=1),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid))
                )
            )

            if errorIndication or errorStatus:
                return None
            else:
                for varBind in varBinds:
                    return str(varBind[1])
        except Exception:
            return None

    @staticmethod
    def sincronizar_dc1():

        resultado = subprocess.run(
            ["net", "view", r"\\dc1"],
            capture_output=True,
            text=True,
            encoding="cp850"
        )

        if resultado.returncode != 0:
            logger.warning(f"Erro ao executar net view no DC1: {resultado.stderr}")
            return

        linhas = resultado.stdout.splitlines()

        for linha in linhas:

            if "Impressão" not in linha:
                continue

            nome = linha.split("Impressão")[0].strip()

            existe = Impressora.query.filter_by(
                nome=nome
            ).first()

            if existe:
                continue

            nova = Impressora(
                nome=nome,
                online=False
            )

            db.session.add(nova)

        db.session.commit()


    @staticmethod
    def atualizar_ips_dc1():

        comando = r"""
        Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Control\Print\Printers" |
        ForEach-Object {

            $printer = Get-ItemProperty $_.PSPath

            [PSCustomObject]@{
                Nome = $_.PSChildName
                Porta = $printer.Port
                Driver = $printer.Driver
            }

        } |
        ConvertTo-Json -Depth 3
        """

        # Executa o PowerShell NO DC1
        comando_remoto = f"""
        Invoke-Command -ComputerName dc1 -ScriptBlock {{
            {comando}
        }}
        """

        resultado = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                comando_remoto
            ],
            capture_output=True,
            text=True,
            encoding="cp850"
        )

        if resultado.returncode != 0:
            logger.error(f"Erro ao consultar Registry do DC1: {resultado.stderr}")
            return

        if not resultado.stdout.strip():
            logger.warning("DC1 não retornou dados de impressoras.")
            return

        try:
            impressoras = json.loads(
                resultado.stdout
            )
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao interpretar JSON do DC1: {e}")
            logger.debug(f"Saída bruta recebida: {resultado.stdout}")
            return

        # Quando existe apenas uma impressora,
        # o PowerShell retorna um objeto em vez de uma lista.
        if isinstance(impressoras, dict):
            impressoras = [
                impressoras
            ]

        atualizadas = 0

        for item in impressoras:
            nome = item.get("Nome")
            porta = item.get("Porta")

            if not nome or not porta:
                continue

            # Ignora impressoras redirecionadas
            if "(redirected" in nome.lower():
                continue

            # Ignora filas virtuais de software (PDF24, Generic, etc.)
            if any(termo in nome.lower() for termo in cls.TERMOS_VIRTUAIS):
                continue

            # Procura IPv4 dentro da porta
            match = re.search(
                r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
                str(porta)
            )

            if not match:
                continue

            ip = match.group()

            impressora = Impressora.query.filter_by(
                nome=nome
            ).first()

            if not impressora:
                logger.debug(f"Impressora não encontrada no banco: {nome}")
                continue

            impressora.ip = ip
            atualizadas += 1
            logger.info(f"IP atualizado: {nome} -> {ip}")

        db.session.commit()
        logger.info(f"Total de IPs de impressoras atualizados: {atualizadas}")

    @staticmethod
    def _ping(ip, timeout_ms=500):
        """
        Executa um ping único. Isolado em método próprio para poder
        ser disparado em paralelo (ThreadPoolExecutor) para várias
        impressoras ao mesmo tempo, em vez de uma por uma.
        """

        try:
            resultado = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout_ms), ip],
                capture_output=True,
                text=True,
                timeout=(timeout_ms / 1000) + 2  # trava de segurança
            )

            return resultado.returncode == 0

        except Exception:
            return False

    @staticmethod
    def atualizar_status():
        """
        Atualiza o status das impressoras através de Ping e SNMP.

        Dados coletados via SNMP:
        - Número de série
        - Total de páginas impressas
        - Percentual de toner preto
        - Percentual do cilindro

        OTIMIZAÇÃO:
        Antes, cada impressora era pingada e consultada via SNMP de
        forma sequencial (uma de cada vez), então o tempo total era
        a SOMA do tempo de todas. Agora:
          1. Todos os pings são disparados em paralelo (threads).
          2. Todas as consultas SNMP das impressoras online também
             são feitas em paralelo (asyncio).
        O tempo total passa a ser, em média, o do dispositivo mais
        lento, não a soma de todos.
        """

        impressoras = Impressora.query.all()

        # -------------------------------------------------------------
        # 0. Filtra impressoras com IP válido e monta mapa ip -> objeto
        # -------------------------------------------------------------

        impressoras_com_ip = []

        for impressora in impressoras:

            if not impressora.ip:
                continue

            match = re.search(
                r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
                str(impressora.ip)
            )

            if not match:
                continue

            impressoras_com_ip.append(
                (impressora, match.group())
            )

        # -------------------------------------------------------------
        # 1. CHECAGEM DE REDE (ping) EM PARALELO
        # -------------------------------------------------------------

        status_ping = {}  # ip -> bool (online)

        with ThreadPoolExecutor(max_workers=20) as executor:

            futuros = {
                executor.submit(ImpressorasService._ping, ip): ip
                for _, ip in impressoras_com_ip
            }

            for futuro in as_completed(futuros):
                ip = futuros[futuro]
                status_ping[ip] = futuro.result()

        ips_online = [
            ip for _, ip in impressoras_com_ip
            if status_ping.get(ip)
        ]

        # -------------------------------------------------------------
        # 2. CONSULTA SNMP EM LOTE (PARALELA) — só para quem respondeu ping
        # -------------------------------------------------------------

        dados_snmp_por_ip = {}

        if ips_online:
            dados_snmp_por_ip = consultar_impressoras_bulk(ips_online)

        # -------------------------------------------------------------
        # 3. APLICA OS RESULTADOS EM CADA IMPRESSORA
        # -------------------------------------------------------------

        for impressora, ip in impressoras_com_ip:

            impressora.ultimo_check = datetime.now()

            is_online = status_ping.get(ip, False)
            impressora.online = is_online

            # -----------------------------------------------------
            # IMPRESSORA OFFLINE
            # -----------------------------------------------------

            if not is_online:
                impressora.status_detalhado = "Equipamento Offline"
                impressora.necessita_atencao = True
                logger.debug(f"{impressora.nome} ({ip}) -> OFFLINE")
                continue

            try:
                dados_snmp = dados_snmp_por_ip.get(ip, {})
                logger.debug(f"SNMP {impressora.nome} ({ip}): {dados_snmp}")

                # -------------------------------------------------
                # Verifica se houve erro na consulta SNMP
                # -------------------------------------------------
                if not dados_snmp or "erro" in dados_snmp:
                    impressora.status_detalhado = "Erro de Comunicação SNMP"
                    impressora.necessita_atencao = True
                    logger.warning(f"Erro SNMP em {impressora.nome}: {dados_snmp.get('erro', 'sem resposta')}")
                    continue

                # -------------------------------------------------
                # NÚMERO DE SÉRIE
                # -------------------------------------------------
                serial = dados_snmp.get("serial")
                if serial:
                    impressora.serial = serial

                # -------------------------------------------------
                # TOTAL DE PÁGINAS
                # -------------------------------------------------
                paginas = dados_snmp.get("paginas_impressas")
                if paginas is not None:
                    impressora.paginas_impressas = int(paginas)

                # -------------------------------------------------
                # TONER PRETO
                # -------------------------------------------------
                toner = dados_snmp.get("toner_porcentagem")
                impressora.toner_preto = (
                    int(round(float(toner))) if toner is not None else None
                )

                # -------------------------------------------------
                # CILINDRO
                # -------------------------------------------------
                cilindro = dados_snmp.get("cilindro_porcentagem")
                if cilindro is not None:
                    impressora.cilindro = int(round(float(cilindro)))

                # -------------------------------------------------
                # MAC ADDRESS, CONTATO E LOCALIZAÇÃO
                # -------------------------------------------------
                mac = dados_snmp.get("mac_address")
                if mac:
                    impressora.mac_address = mac

                contato = dados_snmp.get("contato")
                if contato:
                    impressora.contato = contato

                local = dados_snmp.get("local")
                if local:
                    impressora.local = local

                # -------------------------------------------------
                # STATUS
                # -------------------------------------------------
                impressora.status_detalhado = "Pronta / Operacional"
                impressora.necessita_atencao = False

                logger.info(
                    f"{impressora.nome} ({ip}) -> ONLINE | "
                    f"Toner: {impressora.toner_preto}% | "
                    f"Cilindro: {impressora.cilindro}% | "
                    f"Páginas: {impressora.paginas_impressas}"
                )

            except Exception as e:
                logger.error(f"Erro ao atualizar {impressora.nome} ({ip}): {e}")
                impressora.online = False
                impressora.status_detalhado = "Erro de Comunicação"
                impressora.necessita_atencao = True

        # ---------------------------------------------------------
        # SALVA TODAS AS ALTERAÇÕES
        # ---------------------------------------------------------
        db.session.commit()
        logger.info("Atualização das impressoras finalizada com sucesso.")

    @staticmethod
    def consultar_interface_web(ip):
        try:
            url = f"http://{ip}/general/status.html"
            resposta = requests.get(
                url,
                timeout=5
            )
            if resposta.status_code != 200:
                return None
            return resposta.text
        except Exception as e:
            logger.warning(f"Falha ao consultar interface web da impressora {ip}: {e}")
            return None
        
    # =============================================================
    # PAINEL DE ATENÇÃO (Home) - Impressoras + Suprimentos críticos
    # =============================================================

    LIMITE_PERCENTUAL_BAIXO = 20
    LIMITE_PERCENTUAL_CRITICO = 10

    @staticmethod
    def obter_itens_atencao():
        """
        Monta a lista de itens críticos para o painel da Home:
        - Impressoras online com toner ou cilindro abaixo do limite.
        - Famílias de suprimentos com estoque de toner ou cilindro
          abaixo de 1 unidade.
        """

        itens = []

        # --- Impressoras com toner/cilindro baixo (só as online) ---

        impressoras = Impressora.query.filter_by(online=True).all()

        for impressora in impressoras:

            if (
                impressora.toner_preto is not None
                and impressora.toner_preto <= ImpressorasService.LIMITE_PERCENTUAL_BAIXO
            ):
                itens.append({
                    "tipo": "impressora",
                    "nome": impressora.nome,
                    "detalhe": "Toner preto baixo",
                    "valor": f"{impressora.toner_preto}%",
                    "severidade": (
                        "critico"
                        if impressora.toner_preto <= ImpressorasService.LIMITE_PERCENTUAL_CRITICO
                        else "alerta"
                    ),
                })

            if (
                impressora.cilindro is not None
                and impressora.cilindro <= ImpressorasService.LIMITE_PERCENTUAL_BAIXO
            ):
                itens.append({
                    "tipo": "impressora",
                    "nome": impressora.nome,
                    "detalhe": "Cilindro baixo",
                    "valor": f"{impressora.cilindro}%",
                    "severidade": (
                        "critico"
                        if impressora.cilindro <= ImpressorasService.LIMITE_PERCENTUAL_CRITICO
                        else "alerta"
                    ),
                })

        # --- Suprimentos com estoque abaixo de 1 unidade ---

        familias = EstoqueSuprimento.query.all()

        for familia in familias:

            if familia.quantidade_toner < 1:
                itens.append({
                    "tipo": "suprimento",
                    "nome": familia.nome_familia,
                    "detalhe": "Toner em estoque",
                    "valor": f"{familia.quantidade_toner} un.",
                    "severidade": "critico",
                })

            if familia.quantidade_cilindro < 1:
                itens.append({
                    "tipo": "suprimento",
                    "nome": familia.nome_familia,
                    "detalhe": "Cilindro em estoque",
                    "valor": f"{familia.quantidade_cilindro} un.",
                    "severidade": "critico",
                })

        return itens

    @classmethod
    def listar_impressoras_com_contagem(cls):
        """Retorna as impressoras físicas que estão online ou possuem contagem de páginas."""
        condicoes_exclusao = [
            ~Impressora.nome.ilike(f"%{termo}%")
            for termo in cls.TERMOS_VIRTUAIS
        ]
        return Impressora.query.filter(
            *condicoes_exclusao,
            db.or_(
                Impressora.online.is_(True),
                Impressora.paginas_impressas > 0
            )
        ).order_by(
            Impressora.online.desc(),
            Impressora.paginas_impressas.desc(),
            Impressora.nome.asc()
        ).all()

    @staticmethod
    def gerar_pdf_contadores():
        """
        Gera um relatório em PDF em orientação Paisagem (Landscape) dividido em 2 páginas:
        - Página 1: Somente impressoras Online e Funcionais (com contagem atualizada e dados de rede).
        - Página 2: Somente impressoras Offline / Sem comunicação (desligadas ou sem IP cadastrado).
        """
        # Filtrar apenas impressoras físicas (descarta filas virtuais)
        condicoes_exclusao = [
            ~Impressora.nome.ilike(f"%{termo}%")
            for termo in ImpressorasService.TERMOS_VIRTUAIS
        ]

        # Página 1: Impressoras Online OU que possuem contagem de páginas (> 0)
        impressoras_pagina1 = ImpressorasService.listar_impressoras_com_contagem()

        # Página 2: Impressoras sem contagem de páginas (0 ou None e Offline)
        impressoras_pagina2 = Impressora.query.filter(
            *condicoes_exclusao,
            Impressora.online.is_(False),
            db.or_(
                Impressora.paginas_impressas.is_(None),
                Impressora.paginas_impressas == 0
            )
        ).order_by(
            Impressora.nome.asc()
        ).all()

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            leftMargin=30,
            rightMargin=30,
            topMargin=30,
            bottomMargin=35
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontSize=15,
            leading=18,
            textColor=colors.HexColor('#0f172a'),
            spaceAfter=2
        )
        subtitle_style = ParagraphStyle(
            'DocSubTitle',
            parent=styles['Normal'],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=12
        )
        th_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=11,
            textColor=colors.HexColor('#1e293b')
        )
        td_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor('#1e293b')
        )

        col_widths = [125, 120, 160, 160, 115, 100]

        def criar_estilo_tabela(num_linhas):
            t_style = TableStyle([
                ('LINEBELOW', (0, 0), (-1, 0), 1.2, colors.HexColor('#94a3b8')),
                ('TOPPADDING', (0, 0), (-1, 0), 5),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ])
            for i in range(1, num_linhas):
                if i % 2 == 0:
                    t_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f1f5f9'))
                else:
                    t_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#ffffff'))
            return t_style

        elements = []
        agora = datetime.now()
        agora_str = agora.strftime("%d/%m/%Y %H:%M")

        # ==================================================================
        # PÁGINA 1: IMPRESSORAS COM CONTAGEM DE PÁGINAS / ONLINE
        # ==================================================================
        elements.append(Paragraph(
            "Relatório de Contagem de Páginas — Equipamentos Monitorados",
            title_style
        ))
        elements.append(Paragraph(
            f"Central de Chamados | Emitido em: {agora_str} | Equipamentos com contagem de páginas: {len(impressoras_pagina1)}",
            subtitle_style
        ))

        headers_p1 = [
            Paragraph("Número de série", th_style),
            Paragraph("Endereço MAC", th_style),
            Paragraph("Local", th_style),
            Paragraph("Contato", th_style),
            Paragraph("Contagem total de páginas", th_style),
            Paragraph("Status atualizado", th_style),
        ]
        table_data_p1 = [headers_p1]

        for imp in impressoras_pagina1:
            serial = imp.serial or imp.nome
            mac = imp.mac_address or ""

            if imp.local and imp.local.strip():
                local = imp.local.strip()
            elif imp.sala and imp.sala != "Não Informado":
                local = imp.sala.strip()
            else:
                m = re.search(r'\((.*?)\)', imp.nome or '')
                local = m.group(1).strip() if m else ""

            contato = imp.contato or ""
            paginas = str(imp.paginas_impressas or 0)
            dt_atualizado = imp.ultimo_check.strftime("%d/%m/%Y %H:%M") if imp.ultimo_check else agora_str

            row = [
                Paragraph(serial, td_style),
                Paragraph(mac, td_style),
                Paragraph(local, td_style),
                Paragraph(contato, td_style),
                Paragraph(paginas, td_style),
                Paragraph(dt_atualizado, td_style),
            ]
            table_data_p1.append(row)

        table_p1 = Table(
            table_data_p1,
            colWidths=col_widths,
            style=criar_estilo_tabela(len(table_data_p1)),
            repeatRows=1
        )
        elements.append(table_p1)

        # ==================================================================
        # QUEBRA PARA A PÁGINA 2: IMPRESSORAS SEM CONTAGEM / SEM COMUNICAÇÃO
        # ==================================================================
        elements.append(PageBreak())

        elements.append(Paragraph(
            "Relatório de Equipamentos Sem Contagem / Sem Comunicação",
            title_style
        ))
        elements.append(Paragraph(
            f"Central de Chamados | Equipamentos sem IP cadastrado ou sem resposta na rede | Total: {len(impressoras_pagina2)}",
            subtitle_style
        ))

        headers_p2 = [
            Paragraph("Número de série / Equipamento", th_style),
            Paragraph("Endereço MAC / IP", th_style),
            Paragraph("Local", th_style),
            Paragraph("Contato", th_style),
            Paragraph("Última contagem", th_style),
            Paragraph("Status atualizado", th_style),
        ]
        table_data_p2 = [headers_p2]

        for imp in impressoras_pagina2:
            serial = imp.serial if imp.serial else imp.nome
            mac_ip = imp.mac_address or (f"IP: {imp.ip}" if imp.ip else "Sem IP cadastrado")

            if imp.local and imp.local.strip():
                local = imp.local.strip()
            elif imp.sala and imp.sala != "Não Informado":
                local = imp.sala.strip()
            else:
                m = re.search(r'\((.*?)\)', imp.nome or '')
                local = m.group(1).strip() if m else ""

            contato = imp.contato or ""
            paginas = str(imp.paginas_impressas or 0)

            if imp.ultimo_check:
                dt_atualizado = imp.ultimo_check.strftime("%d/%m/%Y %H:%M")
            elif imp.paginas_impressas and imp.paginas_impressas > 0:
                dt_atualizado = "Leitura anterior"
            else:
                dt_atualizado = "Sem comunicação"

            row = [
                Paragraph(serial, td_style),
                Paragraph(mac_ip, td_style),
                Paragraph(local, td_style),
                Paragraph(contato, td_style),
                Paragraph(paginas, td_style),
                Paragraph(dt_atualizado, td_style),
            ]
            table_data_p2.append(row)

        table_p2 = Table(
            table_data_p2,
            colWidths=col_widths,
            style=criar_estilo_tabela(len(table_data_p2)),
            repeatRows=1
        )
        elements.append(table_p2)

        doc.build(elements, canvasmaker=NumberedCanvas)
        buf.seek(0)
        return buf
