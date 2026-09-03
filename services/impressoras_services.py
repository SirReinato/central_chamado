from models import Impressora, db


import subprocess
import json
import re
import requests

from datetime import datetime

from pysnmp.hlapi import *

from services.snmp_service import consultar_impressora


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
    def atualizar_status():
        """
        Atualiza o status das impressoras através de Ping e SNMP.

        Dados coletados via SNMP:
        - Número de série
        - Total de páginas impressas
        - Percentual de toner preto
        - Percentual do cilindro
        """

        impressoras = Impressora.query.all()

        for impressora in impressoras:

            # -----------------------------------------------------
            # Validação do IP
            # -----------------------------------------------------

            if not impressora.ip:
                continue

            match = re.search(
                r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
                str(impressora.ip)
            )

            if not match:
                continue

            ip = match.group()

            try:

                # -------------------------------------------------
                # 1. CHECAGEM DE REDE
                # -------------------------------------------------

                resultado_ping = subprocess.run(
                    ["ping", "-n", "1", "-w", "500", ip],
                    capture_output=True,
                    text=True
                )

                is_online = (
                    resultado_ping.returncode == 0
                )

                impressora.online = is_online

                impressora.ultimo_check = datetime.now()

                # -------------------------------------------------
                # IMPRESSORA OFFLINE
                # -------------------------------------------------

                if not is_online:

                    impressora.status_detalhado = (
                        "Equipamento Offline"
                    )

                    impressora.necessita_atencao = True

                    print(
                        f"{impressora.nome} ({ip}) -> OFFLINE"
                    )

                    continue

                # -------------------------------------------------
                # 2. CONSULTA SNMP
                # -------------------------------------------------

                dados_snmp = consultar_impressora(ip)

                print(
                    f"SNMP {impressora.nome} ({ip}): "
                    f"{dados_snmp}"
                )

                # -------------------------------------------------
                # Verifica se houve erro na consulta SNMP
                # -------------------------------------------------

                if "erro" in dados_snmp:

                    impressora.status_detalhado = (
                        "Erro de Comunicação SNMP"
                    )

                    impressora.necessita_atencao = True

                    print(
                        f"Erro SNMP em {impressora.nome}: "
                        f"{dados_snmp['erro']}"
                    )

                    continue

                # -------------------------------------------------
                # 3. NÚMERO DE SÉRIE
                # -------------------------------------------------

                serial = dados_snmp.get("serial")

                if serial:
                    impressora.serial = serial

                # -------------------------------------------------
                # 4. TOTAL DE PÁGINAS
                # -------------------------------------------------

                paginas = dados_snmp.get(
                    "paginas_impressas"
                )

                if paginas is not None:

                    impressora.paginas_impressas = int(
                        paginas
                    )

                # -------------------------------------------------
                # 5. TONER PRETO
                # -------------------------------------------------

                toner = dados_snmp.get(
                    "toner_porcentagem"
                )

                if toner is not None:

                    impressora.toner_preto = int(
                        round(float(toner))
                    )

                # -------------------------------------------------
                # 6. CILINDRO
                # -------------------------------------------------

                cilindro = dados_snmp.get(
                    "cilindro_porcentagem"
                )

                if cilindro is not None:

                    impressora.cilindro = int(
                        round(float(cilindro))
                    )

                # -------------------------------------------------
                # 7. STATUS
                # -------------------------------------------------

                impressora.status_detalhado = (
                    "Pronta / Operacional"
                )

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

                impressora.status_detalhado = (
                    "Erro de Comunicação"
                )

                impressora.necessita_atencao = True

        # ---------------------------------------------------------
        # SALVA TODAS AS ALTERAÇÕES
        # ---------------------------------------------------------

        db.session.commit()

        print(
            "Atualização das impressoras finalizada."
        )


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