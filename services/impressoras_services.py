from models import Impressora

class ImpressorasService:

    @staticmethod
    def listar_impressoras():
        return Impressora.query.all()

    @staticmethod
    def descobrir_impressoras():
        pass
    
    @staticmethod
    def atualoizar_status():
        pass
    
    @staticmethod
    def consultar_snmp(ip):
        pass
    
