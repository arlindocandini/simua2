import os
import uuid
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import piexif
from flask import current_app
from werkzeug.utils import secure_filename

class ImageService:
    """Serviço para processamento de imagens e metadados EXIF"""
    
    @staticmethod
    def allowed_file(filename):
        """Verifica se extensão do arquivo é permitida"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
    
    @staticmethod
    def extrair_metadados_exif(imagem_path):
        """
        Extrai metadados EXIF da imagem, incluindo GPS
        
        Args:
            imagem_path: Caminho da imagem
            
        Returns:
            dict: Dicionário com metadados (latitude, longitude, timestamp, etc)
        """
        try:
            image = Image.open(imagem_path)
            exif_dict = piexif.load(image.info.get('exif', b''))
            
            metadados = {
                'tem_exif': True,
                'tem_gps': False,
                'latitude': None,
                'longitude': None,
                'altitude': None,
                'timestamp': None,
                'camera_marca': None,
                'camera_modelo': None,
                'dados_completos': {}
            }
            
            # Extrair informações da câmera
            if '0th' in exif_dict:
                zeroth_ifd = exif_dict['0th']
                metadados['camera_marca'] = zeroth_ifd.get(piexif.ImageIFD.Make, '').decode('utf-8') if isinstance(zeroth_ifd.get(piexif.ImageIFD.Make), bytes) else zeroth_ifd.get(piexif.ImageIFD.Make)
                metadados['camera_modelo'] = zeroth_ifd.get(piexif.ImageIFD.Model, '').decode('utf-8') if isinstance(zeroth_ifd.get(piexif.ImageIFD.Model), bytes) else zeroth_ifd.get(piexif.ImageIFD.Model)
            
            # Extrair timestamp
            if 'Exif' in exif_dict:
                exif_ifd = exif_dict['Exif']
                dt_original = exif_ifd.get(piexif.ExifIFD.DateTimeOriginal)
                if dt_original:
                    try:
                        dt_str = dt_original.decode('utf-8') if isinstance(dt_original, bytes) else dt_original
                        metadados['timestamp'] = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                    except:
                        pass
            
            # Extrair GPS
            if 'GPS' in exif_dict and exif_dict['GPS']:
                metadados['tem_gps'] = True
                gps_info = exif_dict['GPS']
                
                # Converter coordenadas GPS
                if piexif.GPSIFD.GPSLatitude in gps_info and piexif.GPSIFD.GPSLongitude in gps_info:
                    lat = ImageService._converter_coordenada_gps(
                        gps_info[piexif.GPSIFD.GPSLatitude],
                        gps_info.get(piexif.GPSIFD.GPSLatitudeRef, b'N')
                    )
                    lon = ImageService._converter_coordenada_gps(
                        gps_info[piexif.GPSIFD.GPSLongitude],
                        gps_info.get(piexif.GPSIFD.GPSLongitudeRef, b'E')
                    )
                    
                    metadados['latitude'] = lat
                    metadados['longitude'] = lon
                
                # Altitude (se disponível)
                if piexif.GPSIFD.GPSAltitude in gps_info:
                    alt_tuple = gps_info[piexif.GPSIFD.GPSAltitude]
                    metadados['altitude'] = alt_tuple[0] / alt_tuple[1]
            
            metadados['dados_completos'] = exif_dict
            
            return metadados
            
        except Exception as e:
            current_app.logger.error(f'Erro ao extrair EXIF: {str(e)}')
            return {
                'tem_exif': False,
                'tem_gps': False,
                'erro': str(e)
            }
    
    @staticmethod
    def _converter_coordenada_gps(coordenada, ref):
        """
        Converte coordenada GPS do formato EXIF para decimal
        
        Args:
            coordenada: Tupla ((graus_num, graus_den), (min_num, min_den), (seg_num, seg_den))
            ref: Referência (N/S para latitude, E/W para longitude)
            
        Returns:
            float: Coordenada em formato decimal
        """
        graus = coordenada[0][0] / coordenada[0][1]
        minutos = coordenada[1][0] / coordenada[1][1]
        segundos = coordenada[2][0] / coordenada[2][1]
        
        decimal = graus + (minutos / 60.0) + (segundos / 3600.0)
        
        # Converter para negativo se S ou W
        if ref in [b'S', b'W', 'S', 'W']:
            decimal = -decimal
        
        return decimal
    
    @staticmethod
    def adicionar_metadados_gps(imagem_path, latitude, longitude, timestamp=None):
        """
        Adiciona ou atualiza metadados GPS na imagem
        
        Args:
            imagem_path: Caminho da imagem
            latitude: Latitude em decimal
            longitude: Longitude em decimal
            timestamp: Timestamp da captura (opcional)
        """
        try:
            image = Image.open(imagem_path)
            
            # Carrega EXIF existente ou cria novo
            try:
                exif_dict = piexif.load(image.info.get('exif', b''))
            except:
                exif_dict = {'0th': {}, 'Exif': {}, 'GPS': {}, '1st': {}, 'thumbnail': None}
            
            # Converte coordenadas para formato EXIF
            lat_deg = ImageService._decimal_para_dms(abs(latitude))
            lon_deg = ImageService._decimal_para_dms(abs(longitude))
            
            lat_ref = b'N' if latitude >= 0 else b'S'
            lon_ref = b'E' if longitude >= 0 else b'W'
            
            # Adiciona GPS ao EXIF
            exif_dict['GPS'] = {
                piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
                piexif.GPSIFD.GPSLatitudeRef: lat_ref,
                piexif.GPSIFD.GPSLatitude: lat_deg,
                piexif.GPSIFD.GPSLongitudeRef: lon_ref,
                piexif.GPSIFD.GPSLongitude: lon_deg,
            }
            
            # Adiciona timestamp se fornecido
            if timestamp:
                dt_str = timestamp.strftime('%Y:%m:%d %H:%M:%S')
                exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = dt_str.encode('utf-8')
                exif_dict['0th'][piexif.ImageIFD.DateTime] = dt_str.encode('utf-8')
            
            # Salva EXIF na imagem
            exif_bytes = piexif.dump(exif_dict)
            image.save(imagem_path, exif=exif_bytes)
            
            current_app.logger.info(f'GPS adicionado à imagem: {imagem_path}')
            
        except Exception as e:
            current_app.logger.error(f'Erro ao adicionar GPS: {str(e)}')
    
    @staticmethod
    def _decimal_para_dms(decimal):
        """
        Converte coordenada decimal para graus/minutos/segundos (formato EXIF)
        
        Args:
            decimal: Coordenada em formato decimal
            
        Returns:
            tuple: ((graus_num, graus_den), (min_num, min_den), (seg_num, seg_den))
        """
        graus = int(decimal)
        minutos_decimal = (decimal - graus) * 60
        minutos = int(minutos_decimal)
        segundos = (minutos_decimal - minutos) * 60
        
        # Multiplica por 100 para precisão e converte para inteiro
        segundos_int = int(segundos * 100)
        
        return (
            (graus, 1),
            (minutos, 1),
            (segundos_int, 100)
        )
    
    @staticmethod
    def processar_upload(file, latitude=None, longitude=None, camera_id=None):
        """
        Processa upload de imagem completo:
        1. Salva arquivo
        2. Extrai/adiciona metadados GPS
        3. Cria miniatura
        
        Args:
            file: Objeto FileStorage do Flask
            latitude: Latitude (se não houver EXIF)
            longitude: Longitude (se não houver EXIF)
            camera_id: ID da câmera (se aplicável)
            
        Returns:
            dict: {
                'imagem_path': caminho da imagem original,
                'miniatura_path': caminho da miniatura,
                'metadados': metadados extraídos,
                'latitude': latitude final,
                'longitude': longitude final
            }
        """
        # Gerar nome único
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f'{uuid.uuid4().hex}.{ext}'
        
        # Caminhos
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'ocorrencias')
        miniatura_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'miniaturas')
        
        imagem_path = os.path.join(upload_folder, filename)
        miniatura_path = os.path.join(miniatura_folder, filename)
        
        # Salvar imagem original
        file.save(imagem_path)
        
        # Extrair metadados EXIF
        metadados = ImageService.extrair_metadados_exif(imagem_path)
        
        # Determinar coordenadas finais
        lat_final = metadados.get('latitude') or latitude
        lon_final = metadados.get('longitude') or longitude
        
        # Se não tem GPS no EXIF, adicionar
        if not metadados.get('tem_gps') and lat_final and lon_final:
            ImageService.adicionar_metadados_gps(
                imagem_path, 
                lat_final, 
                lon_final,
                metadados.get('timestamp')
            )
            metadados['latitude'] = lat_final
            metadados['longitude'] = lon_final
            metadados['tem_gps'] = True
        
        # Criar miniatura
        ImageService.criar_miniatura(imagem_path, miniatura_path)
        
        return {
            'imagem_path': imagem_path,
            'miniatura_path': miniatura_path,
            'metadados': metadados,
            'latitude': lat_final,
            'longitude': lon_final
        }
    
    @staticmethod
    def criar_miniatura(imagem_path, miniatura_path, tamanho=None):
        """
        Cria miniatura da imagem
        
        Args:
            imagem_path: Caminho da imagem original
            miniatura_path: Caminho onde salvar miniatura
            tamanho: Tamanho da miniatura (padrão: config)
        """
        if tamanho is None:
            tamanho = (current_app.config['THUMBNAIL_SIZE'], 
                      current_app.config['THUMBNAIL_SIZE'])
        
        try:
            image = Image.open(imagem_path)
            image.thumbnail(tamanho, Image.Resampling.LANCZOS)
            image.save(
                miniatura_path, 
                quality=current_app.config['IMAGE_QUALITY'],
                optimize=True
            )
            current_app.logger.info(f'Miniatura criada: {miniatura_path}')
        except Exception as e:
            current_app.logger.error(f'Erro ao criar miniatura: {str(e)}')