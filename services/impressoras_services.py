from models import Impressora, db


import subprocess
import json
import re
import requests

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from pysnmp.hlapi import *

from services.snmp_service import consultar_impressora, consultar_impressoras_bulk


class ImpressorasService:

    @staticmethod
    def listar_impressoras():
        return Impressora.query.all()


    @staticmethod
    def adicionar_impressora(nome, ip, modelo):

        existente = Impressora.query.filter_by(
            ip=ip
        ).first()

        if existente:
            return existente

        impressora = Impressora(
            nome=nome,
            ip=ip,
            modelo=modelo
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
            print(resultado.stderr)
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

            print("Erro ao consultar Registry do DC1:")
            print(resultado.stderr)

            return

        if not resultado.stdout.strip():

            print("DC1 não retornou dados.")

            return

        try:

            impressoras = json.loads(
                resultado.stdout
            )

        except json.JSONDecodeError as e:

            print(
                "Erro ao interpretar JSON:",
                e
            )

            print("Saída recebida:")
            print(resultado.stdout)

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
                print(
                    f"Impressora não encontrada no banco: {nome}"
                )

                continue

            impressora.ip = ip

            atualizadas += 1

            print(
                f"IP atualizado: {nome} -> {ip}"
            )

        db.session.commit()

        print(
            f"Total de IPs atualizados: {atualizadas}"
        )

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

                print(f"{impressora.nome} ({ip}) -> OFFLINE")

                continue

            try:

                dados_snmp = dados_snmp_por_ip.get(ip, {})

                print(
                    f"SNMP {impressora.nome} ({ip}): "
                    f"{dados_snmp}"
                )

                # -------------------------------------------------
                # Verifica se houve erro na consulta SNMP
                # -------------------------------------------------

                if not dados_snmp or "erro" in dados_snmp:

                    impressora.status_detalhado = (
                        "Erro de Comunicação SNMP"
                    )

                    impressora.necessita_atencao = True

                    print(
                        f"Erro SNMP em {impressora.nome}: "
                        f"{dados_snmp.get('erro', 'sem resposta')}"
                    )

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

                # -------------------------------------------------
                # TONER PRETO
                #
                # Alguns modelos (ex.: Brother DCP-8157DN) NAO
                # reportam percentual de toner nem via SNMP nem
                # na propria pagina de manutencao da impressora
                # -- so contam quantas vezes o toner foi trocado.
                # Nesses casos, gravamos None explicitamente para
                # nao deixar um valor antigo "congelado" no banco
                # (era isso que causava o 91% fixo em todas as
                # Brother: o campo nunca era atualizado e ficava
                # com o ultimo valor salvo, seja la qual fosse).
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
                # STATUS
                # -------------------------------------------------

                impressora.status_detalhado = "Pronta / Operacional"
                impressora.necessita_atencao = False

                print(
                    f"{impressora.nome} ({ip}) -> "
                    f"ONLINE | "
                    f"Toner: {impressora.toner_preto}% | "
                    f"Cilindro: {impressora.cilindro}% | "
                    f"Páginas: {impressora.paginas_impressas}"
                )

            except Exception as e:

                print(
                    f"Erro ao atualizar "
                    f"{impressora.nome} ({ip}): {e}"
                )

                impressora.online = False
                impressora.status_detalhado = "Erro de Comunicação"
                impressora.necessita_atencao = True

        # ---------------------------------------------------------
        # SALVA TODAS AS ALTERAÇÕES
        # ---------------------------------------------------------

        db.session.commit()

        print("Atualização das impressoras finalizada.")


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

            print(e)

            return None