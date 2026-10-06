import html
import io
import os
import re
import smtplib
from datetime import datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

from utils.logger import get_logger

logger = get_logger("email_service")


class EmailService:
    """
    Serviço centralizado para envio de e-mails corporativos via SMTP (Exchange / Outlook / Microsoft 365).
    Suporta autenticação com conta pessoal/serviço e envio delegado (Send As / Enviar Como).
    """

    @staticmethod
    def get_smtp_config():
        user = os.environ.get("SMTP_USER", "")
        mail_from_address = os.environ.get("MAIL_FROM_ADDRESS") or "ti@empresa.com.br"
        mail_from_name = os.environ.get("MAIL_FROM_NAME") or "Departamento de TI"
        default_recipient = os.environ.get("MAIL_DEFAULT_RECIPIENT") or mail_from_address

        return {
            "server": os.environ.get("SMTP_SERVER", "smtp.office365.com"),
            "port": int(os.environ.get("SMTP_PORT", 587)),
            "user": user,
            "password": os.environ.get("SMTP_PASSWORD", ""),
            "use_tls": os.environ.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"),
            "use_ssl": os.environ.get("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes"),
            "mail_from_address": mail_from_address,
            "mail_from_name": mail_from_name,
            "default_recipient": default_recipient
        }

    @classmethod
    def enviar_relatorio_impressoras(
        cls, 
        destinatarios, 
        pdf_buffer, 
        impressoras_com_contagem,
        assunto=None,
        mensagem_texto=None,
        incluir_tabela=True
    ):
        """
        Envia o relatório de contagem de páginas por e-mail com o PDF em anexo e um resumo em HTML.

        :param destinatarios: String ou lista de e-mails destinatários.
        :param pdf_buffer: Buffer BytesIO contendo o PDF gerado.
        :param impressoras_com_contagem: Lista de objetos Impressora que possuem contagem de páginas.
        :param assunto: Assunto customizado (opcional).
        :param mensagem_texto: Texto/corpo customizado da mensagem (opcional).
        :param incluir_tabela: Booleano para incluir ou não a tabela com contadores no corpo do e-mail.
        :return: (sucesso: bool, mensagem: str)
        """
        config = cls.get_smtp_config()

        if not config["password"]:
            msg_erro = "Senha de e-mail (SMTP_PASSWORD) não configurada no arquivo .env."
            logger.warning(msg_erro)
            return False, msg_erro

        # Higieniza e valida destinatários contra Header Injection
        if isinstance(destinatarios, str):
            lista_destinatarios = [
                re.sub(r'[\r\n]+', '', d).strip() 
                for d in destinatarios.replace(";", ",").split(",") 
                if d.strip()
            ]
        else:
            lista_destinatarios = [
                re.sub(r'[\r\n]+', '', str(d)).strip() 
                for d in destinatarios 
                if str(d).strip()
            ]

        if not lista_destinatarios:
            return False, "Nenhum endereço de destinatário válido foi informado."

        agora = datetime.now()
        data_formatada = agora.strftime("%d/%m/%Y às %H:%M")
        
        # Assunto customizado ou padrão (higienizado contra CRLF Header Injection)
        if not assunto or not assunto.strip():
            assunto = f"[{config['mail_from_name']}] Relatório de Contagem de Páginas — {agora.strftime('%d/%m/%Y')}"
        else:
            assunto = re.sub(r'[\r\n]+', ' ', assunto).strip()

        # Montagem do e-mail MIME
        msg = MIMEMultipart()
        msg["From"] = f"{config['mail_from_name']} <{config['mail_from_address']}>"
        msg["To"] = ", ".join(lista_destinatarios)
        msg["Subject"] = assunto
        msg["Reply-To"] = config["mail_from_address"]

        # Se o usuário autenticado for diferente da conta From, especifica Sender para compatibilidade SMTP
        if config["user"] and config["user"].lower() != config["mail_from_address"].lower():
            msg["Sender"] = config["user"]

        # Formatação do texto do corpo da mensagem com escape contra HTML Injection
        if mensagem_texto and mensagem_texto.strip():
            linhas_texto = mensagem_texto.strip().split("\n")
            paragrafos = []
            bloco_atual = []
            for linha in linhas_texto:
                l = linha.strip()
                if not l:
                    if bloco_atual:
                        paragrafos.append("<p style='font-size: 14px; line-height: 1.6; margin: 0 0 12px 0; color: #334155;'>" + "<br>".join(bloco_atual) + "</p>")
                        bloco_atual = []
                else:
                    bloco_atual.append(html.escape(l))
            if bloco_atual:
                paragrafos.append("<p style='font-size: 14px; line-height: 1.6; margin: 0 0 12px 0; color: #334155;'>" + "<br>".join(bloco_atual) + "</p>")
            texto_html = "\n".join(paragrafos)
        else:
            texto_html = f"""
            <p style="font-size: 14px; line-height: 1.6; margin: 0 0 10px 0; color: #334155;">Olá equipe,</p>
            <p style="font-size: 14px; line-height: 1.6; margin: 0 0 12px 0; color: #334155;">
                Segue em anexo o relatório oficial consolidado com a <strong>contagem total de páginas</strong> do parque de impressoras, emitido em <strong>{data_formatada}</strong>.
            </p>
            <p style="font-size: 14px; line-height: 1.6; margin: 0 0 12px 0; color: #334155;">Qualquer dúvida, estamos à disposição.</p>
            """

        # Tabela resumo para o corpo do e-mail (se habilitada) com sanitização
        if incluir_tabela and impressoras_com_contagem:
            linhas_html = []
            for idx, imp in enumerate(impressoras_com_contagem, 1):
                nome_esc = html.escape(str(imp.nome or ""))
                local_esc = html.escape(str(imp.local or imp.sala or "-"))
                serial_esc = html.escape(str(imp.serial or "-"))
                pags = f"{imp.paginas_impressas:,}".replace(",", ".") if imp.paginas_impressas else "0"
                linhas_html.append(
                    f"""
                    <tr style="background-color: {'#f8fafc' if idx % 2 == 0 else '#ffffff'};">
                        <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px; color: #1e293b;"><strong>{nome_esc}</strong></td>
                        <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px; color: #475569;">{serial_esc}</td>
                        <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px; color: #475569;">{local_esc}</td>
                        <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 14px; text-align: right; color: #0f172a; font-weight: 600;">{pags}</td>
                    </tr>
                    """
                )

            tabela_html = f"""
            <div style="margin: 20px 0;">
                <h4 style="margin: 0 0 10px 0; font-size: 13px; color: #0f172a; text-transform: uppercase; letter-spacing: 0.5px;">Resumo dos Equipamentos Monitorados ({len(impressoras_com_contagem)})</h4>
                <table style="width: 100%; border-collapse: collapse; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
                    <thead>
                        <tr style="background-color: #f1f5f9; text-align: left;">
                            <th style="padding: 10px 12px; font-size: 12px; color: #475569; border-bottom: 2px solid #cbd5e1;">Impressora</th>
                            <th style="padding: 10px 12px; font-size: 12px; color: #475569; border-bottom: 2px solid #cbd5e1;">Nº Série</th>
                            <th style="padding: 10px 12px; font-size: 12px; color: #475569; border-bottom: 2px solid #cbd5e1;">Local</th>
                            <th style="padding: 10px 12px; font-size: 12px; color: #475569; border-bottom: 2px solid #cbd5e1; text-align: right;">Total Páginas</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(linhas_html)}
                    </tbody>
                </table>
            </div>
            """
        else:
            tabela_html = ""

        # Aviso de anexo (se existir PDF)
        aviso_anexo_html = """
        <div style="background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 12px 16px; border-radius: 6px; margin: 20px 0 16px 0;">
            <p style="margin: 0; font-size: 13px; color: #166534;">
                📎 <strong>Documento Completo em Anexo:</strong> O relatório detalhado de 2 páginas (com endereços MAC, contatos e equipamentos offline) está anexado a esta mensagem em formato PDF.
            </p>
        </div>
        """ if pdf_buffer else ""

        corpo_html = f"""
        <!DOCTYPE html>
        <html lang="pt-br">
        <head>
            <meta charset="UTF-8">
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f1f5f9; padding: 24px; color: #334155; margin: 0;">
            <div style="max-width: 680px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;">
                
                <!-- Cabeçalho -->
                <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 24px; color: #ffffff;">
                    <h2 style="margin: 0 0 6px 0; font-size: 20px; font-weight: 700; color: #e2e8f0;">Relatório de Contagem de Páginas</h2>
                    <p style="margin: 0; font-size: 13px; color: #94a3b8;">{config['mail_from_name']}</p>
                </div>

                <!-- Conteúdo -->
                <div style="padding: 24px;">
                    {texto_html}
                    {tabela_html}
                    {aviso_anexo_html}

                    <p style="font-size: 12px; color: #64748b; margin-bottom: 0;">
                        Mensagem gerada pelo sistema Central de Chamados & Monitoramento.
                    </p>
                </div>

                <!-- Rodapé -->
                <div style="background-color: #f8fafc; padding: 14px 24px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center;">
                    Enviado por <strong>{config['mail_from_address']}</strong>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(corpo_html, "html", "utf-8"))

        # Anexo do PDF
        nome_anexo = f"relatorio_contagem_paginas_{agora.strftime('%Y%m%d_%H%M')}.pdf"
        parte_anexo = MIMEBase("application", "pdf")
        parte_anexo.set_payload(pdf_buffer.getvalue())
        encoders.encode_base64(parte_anexo)
        parte_anexo.add_header("Content-Disposition", f'attachment; filename="{nome_anexo}"')
        msg.attach(parte_anexo)

        # Envio SMTP via Exchange / Outlook / Microsoft 365
        try:
            logger.info(
                f"Conectando ao servidor SMTP {config['server']}:{config['port']} (SSL={config['use_ssl']}, TLS={config['use_tls']}) "
                f"com usuário {config['user']} para enviar como {config['mail_from_address']}..."
            )

            smtp_class = smtplib.SMTP_SSL if config["use_ssl"] else smtplib.SMTP
            with smtp_class(config["server"], config["port"], timeout=25) as servidor:
                servidor.ehlo()
                if config["use_tls"] and not config["use_ssl"]:
                    servidor.starttls()
                    servidor.ehlo()

                if config["user"] and config["password"]:
                    servidor.login(config["user"], config["password"])

                # Tenta enviar com o envelope do mail_from_address (Send As / Enviar Como no Exchange)
                envelope_sender = config["mail_from_address"] or config["user"]
                try:
                    servidor.sendmail(envelope_sender, lista_destinatarios, msg.as_string())
                except smtplib.SMTPSenderRefused as err_sender:
                    logger.warning(
                        f"Envelope sender {envelope_sender} recusado pelo servidor ({err_sender}). "
                        f"Tentando novamente com a conta autenticada {config['user']}..."
                    )
                    servidor.sendmail(config["user"], lista_destinatarios, msg.as_string())

            logger.info(f"Relatório enviado com sucesso para: {', '.join(lista_destinatarios)}")
            return True, f"Relatório enviado com sucesso para {', '.join(lista_destinatarios)}!"

        except smtplib.SMTPAuthenticationError as e:
            msg_erro = f"Falha de autenticação no servidor de e-mail ({config['user']}). Verifique o usuário e a senha: {e}"
            logger.error(msg_erro)
            return False, msg_erro
        except Exception as e:
            msg_erro = f"Erro ao enviar e-mail via SMTP ({config['server']}:{config['port']}): {str(e)}"
            logger.error(msg_erro, exc_info=True)
            return False, msg_erro
