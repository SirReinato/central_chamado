from models import Impressora, db
import subprocess
from datetime import datetime
import re
import json

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
    def atualizar_status():

        impressoras = Impressora.query.all()

        for impressora in impressoras:

            if not impressora.ip:
                continue

            # Extrai apenas um IP válido
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
    def consultar_snmp(ip):
        pass
    
