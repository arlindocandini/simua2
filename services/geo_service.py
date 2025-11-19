# app/services/geo_service.py
import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from flask import current_app

class GeoService:
    """Serviço para geocodificação e geocodificação reversa"""
    
    def __init__(self):
        self.geocoder = Nominatim(
            user_agent=current_app.config.get('NOMINATIM_USER_AGENT', 'ocorrencias_urbanas/1.0'),
            timeout=10
        )
        self._cache = {}  # Cache simples em memória
    
    def obter_endereco(self, latitude, longitude, usar_cache=True):
        """
        Obtém endereço a partir de coordenadas (geocodificação reversa)
        
        Args:
            latitude: Latitude
            longitude: Longitude
            usar_cache: Se True, usa cache para evitar requisições repetidas
            
        Returns:
            str: Endereço completo formatado
        """
        # Chave do cache
        cache_key = f"{latitude},{longitude}"
        
        # Verificar cache
        if usar_cache and cache_key in self._cache:
            current_app.logger.info(f'Endereço encontrado no cache: {cache_key}')
            return self._cache[cache_key]
        
        try:
            # Tentativas com backoff exponencial
            max_tentativas = 3
            for tentativa in range(max_tentativas):
                try:
                    location = self.geocoder.reverse(
                        f"{latitude}, {longitude}",
                        language='pt-BR',
                        exactly_one=True
                    )
                    
                    if location:
                        endereco = location.address
                        
                        # Salvar no cache
                        if usar_cache:
                            self._cache[cache_key] = endereco
                        
                        return endereco
                    else:
                        return f"Coordenadas: ({latitude}, {longitude})"
                    
                except GeocoderTimedOut:
                    if tentativa < max_tentativas - 1:
                        time.sleep(2 ** tentativa)  # Backoff exponencial
                        continue
                    else:
                        current_app.logger.warning(
                            f'Timeout ao buscar endereço: {latitude}, {longitude}'
                        )
                        return f"Coordenadas: ({latitude}, {longitude})"
                        
        except GeocoderServiceError as e:
            current_app.logger.error(f'Erro no serviço de geocodificação: {str(e)}')
            return f"Coordenadas: ({latitude}, {longitude})"
        except Exception as e:
            current_app.logger.error(f'Erro inesperado ao buscar endereço: {str(e)}')
            return f"Coordenadas: ({latitude}, {longitude})"
    
    def obter_coordenadas(self, endereco):
        """
        Obtém coordenadas a partir de endereço (geocodificação)
        
        Args:
            endereco: Endereço textual
            
        Returns:
            tuple: (latitude, longitude) ou (None, None) se não encontrar
        """
        try:
            location = self.geocoder.geocode(endereco, language='pt-BR')
            
            if location:
                return (location.latitude, location.longitude)
            else:
                return (None, None)
                
        except Exception as e:
            current_app.logger.error(f'Erro ao buscar coordenadas: {str(e)}')
            return (None, None)
    
    def limpar_cache(self):
        """Limpa cache de endereços"""
        self._cache = {}
        current_app.logger.info('Cache de endereços limpo')

# Singleton global (será inicializado na primeira importação)
_geo_service_instance = None

def get_geo_service():
    """
    Retorna instância singleton do GeoService
    
    Returns:
        GeoService: Instância do serviço
    """
    global _geo_service_instance
    if _geo_service_instance is None:
        _geo_service_instance = GeoService()
    return _geo_service_instance