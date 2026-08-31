from models import Impressora, db

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
    def descobrir_impressoras():
        pass
    
    @staticmethod
    def atualoizar_status():
        pass
    
    @staticmethod
    def consultar_snmp(ip):
        pass
    
