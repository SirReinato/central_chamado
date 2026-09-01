from models import Impressora, db

import subprocess
import json
import re
import requests

from datetime import datetime


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

        impressoras = Impressora.query.all()

        for impressora in impressoras:

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

                resultado = subprocess.run(
                    ["ping", "-n", "1", "-w", "500", ip],
                    capture_output=True,
                    text=True
                )

                impressora.online = (
                    resultado.returncode == 0
                )

                impressora.ultimo_check = datetime.now()

            except Exception as e:

                print(
                    f"Erro ao verificar {ip}: {e}"
                )

                impressora.online = False

        db.session.commit()


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