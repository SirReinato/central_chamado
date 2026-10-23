import io
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

class AssinaturaService:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    BASE_TEMPLATE_PATH = os.path.join(BASE_DIR, 'static', 'img', 'assinatura_base_template.png')
    PLACEHOLDER_PATH = os.path.join(BASE_DIR, 'static', 'img', 'avatar_placeholder.png')
    FONT_BOLD_PATH = os.path.join(BASE_DIR, 'static', 'fonts', 'Montserrat-Bold.ttf')
    FONT_ITALIC_PATH = os.path.join(BASE_DIR, 'static', 'fonts', 'Montserrat-Italic.ttf')

    LARGURA = 637
    ALTURA = 174

    @classmethod
    def gerar_assinatura(cls, nome, setor, diretoria, email, telefone, foto_file=None):
        """
        Gera uma assinatura de e-mail corporativa idêntica ao modeloPadrãoatualizado.png.
        Dimensões oficiais nativas: 637 x 174 px.
        Com recorte circular perfeitamente suave e algoritmo de supernitidez fotográfica.
        """
        if not os.path.exists(cls.BASE_TEMPLATE_PATH):
            raise FileNotFoundError(f"Template base não encontrado em {cls.BASE_TEMPLATE_PATH}")

        template = Image.open(cls.BASE_TEMPLATE_PATH).convert('RGBA')

        # 1. Tratar foto do colaborador com recorte circular suave e supernitidez
        # Centro geométrico da moldura: (85.5, 87.0), raio de 49px (diâmetro 98px)
        cx, cy = 85.5, 87.0
        r_photo = 49.0
        diam = int(round(r_photo * 2))  # 98px
        px = int(round(cx - r_photo))   # 36 ou 37
        py = int(round(cy - r_photo))   # 38

        photo_img = None
        if foto_file:
            try:
                photo_img = Image.open(foto_file).convert('RGBA')
            except Exception:
                photo_img = None

        if photo_img:
            # Crop central 1:1 quadrado
            pw, ph = photo_img.size
            min_dim = min(pw, ph)
            left = (pw - min_dim) // 2
            top = (ph - min_dim) // 2
            cropped = photo_img.crop((left, top, left + min_dim, top + min_dim))

            # Supersampling 4x para antialiasing perfeito (elimina serrilhado)
            scale_ss = 4
            ss_size = diam * scale_ss
            photo_ss = cropped.resize((ss_size, ss_size), Image.Resampling.LANCZOS)

            mask_ss = Image.new('L', (ss_size, ss_size), 0)
            d_ss = ImageDraw.Draw(mask_ss)
            d_ss.ellipse((0, 0, ss_size - 1, ss_size - 1), fill=255)

            photo_final = photo_ss.resize((diam, diam), Image.Resampling.LANCZOS)
            mask_final = mask_ss.resize((diam, diam), Image.Resampling.LANCZOS)

            # Algoritmo de Supernitidez Fotográfica (Smart Sharpen):
            # 1. Recupera micro-detalhes de olhos, cabelo, sorriso e contornos faciais
            photo_final = photo_final.filter(ImageFilter.UnsharpMask(radius=1.2, percent=140, threshold=2))

            # 2. Leve realce de contraste para a foto não parecer desbotada
            enhancer_contrast = ImageEnhance.Contrast(photo_final)
            photo_final = enhancer_contrast.enhance(1.06)

            # 3. Leve realce de vivacidade de cores
            enhancer_color = ImageEnhance.Color(photo_final)
            photo_final = enhancer_color.enhance(1.04)

            template.paste(photo_final, (px, py), mask_final)
        elif os.path.exists(cls.PLACEHOLDER_PATH):
            placeholder = Image.open(cls.PLACEHOLDER_PATH).convert('RGBA')
            scale_ss = 4
            ss_size = diam * scale_ss
            photo_ss = placeholder.resize((ss_size, ss_size), Image.Resampling.LANCZOS)

            mask_ss = Image.new('L', (ss_size, ss_size), 0)
            d_ss = ImageDraw.Draw(mask_ss)
            d_ss.ellipse((0, 0, ss_size - 1, ss_size - 1), fill=255)

            photo_final = photo_ss.resize((diam, diam), Image.Resampling.LANCZOS)
            mask_final = mask_ss.resize((diam, diam), Image.Resampling.LANCZOS)

            template.paste(photo_final, (px, py), mask_final)

        # 2. Carregar tipografia oficial Montserrat
        draw = ImageDraw.Draw(template)

        try:
            font_nome = ImageFont.truetype(cls.FONT_BOLD_PATH, 16)
            font_nome.set_variation_by_name('Bold')
        except Exception:
            font_nome = ImageFont.load_default()

        try:
            font_setor = ImageFont.truetype(cls.FONT_BOLD_PATH, 14)
            font_setor.set_variation_by_name('Medium')
        except Exception:
            font_setor = ImageFont.load_default()

        try:
            font_diretoria = ImageFont.truetype(cls.FONT_ITALIC_PATH, 12)
            font_diretoria.set_variation_by_name('SemiBold Italic')
        except Exception:
            font_diretoria = ImageFont.load_default()

        try:
            font_contato = ImageFont.truetype(cls.FONT_BOLD_PATH, 11)
            font_contato.set_variation_by_name('Medium')
        except Exception:
            font_contato = ImageFont.load_default()

        # Cores institucionais fiéis ao modelo
        COR_NOME = (0, 20, 75)
        COR_SETOR = (59, 114, 195)
        COR_DIRETORIA = (115, 118, 122)
        COR_CONTATO = (130, 130, 130)

        # 3. Desenhar campos de texto alinhados
        if nome:
            draw.text((180, 41), str(nome).strip(), font=font_nome, fill=COR_NOME)
        if setor:
            draw.text((179, 64), str(setor).strip(), font=font_setor, fill=COR_SETOR)
        if diretoria:
            draw.text((179, 88), str(diretoria).strip(), font=font_diretoria, fill=COR_DIRETORIA)
        if email:
            draw.text((179, 115), str(email).strip(), font=font_contato, fill=COR_CONTATO)
        if telefone:
            draw.text((179, 130), str(telefone).strip(), font=font_contato, fill=COR_CONTATO)

        output = io.BytesIO()
        template.save(output, format='PNG')
        output.seek(0)
        return output
