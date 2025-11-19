from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required
from sqlalchemy import desc, func
from app import db, socketio, csrf
from app.models import Camera, Ocorrencia
from app.utils.decorators import gestor_required
from app.services.ia_service import IAService
from app.services.geo_service import get_geo_service
from datetime import datetime, timedelta
import requests
import base64
import os
import uuid as uuid_lib

cameras_bp = Blueprint('cameras', __name__)

@cameras_bp.route('/')
@cameras_bp.route('/lista')
@login_required
@gestor_required
def lista():
    """Lista todas as câmeras"""
    # Obter câmeras com contagem de ocorrências
    cameras = db.session.query(
        Camera,
        func.count(Ocorrencia.id).label('total_ocorrencias')
    ).outerjoin(
        Ocorrencia, Camera.id == Ocorrencia.camera_id
    ).group_by(Camera.id).all()
    
    # Separar por status
    online = []
    offline = []
    manutencao = []
    
    for camera, total_occ in cameras:
        camera_dict = camera.to_dict()
        camera_dict['total_ocorrencias'] = total_occ
        
        # Verificar se está online (última captura < 5 min)
        if camera.ultima_captura_at:
            diff = datetime.utcnow() - camera.ultima_captura_at
            if diff.total_seconds() > 300:  # 5 minutos
                camera.status = 'offline'
        
        if camera.status == 'online':
            online.append(camera_dict)
        elif camera.status == 'offline':
            offline.append(camera_dict)
        else:
            manutencao.append(camera_dict)
    
    db.session.commit()  # Salvar mudanças de status
    
    return render_template('cameras/lista.html',
                         online=online,
                         offline=offline,
                         manutencao=manutencao,
                         total_online=len(online),
                         total_offline=len(offline),
                         total_manutencao=len(manutencao))

@cameras_bp.route('/<uuid:id>')
@login_required
@gestor_required
def detalhes(id):
    """Detalhes de uma câmera específica"""
    camera = Camera.query.get_or_404(id)
    
    # Estatísticas de ocorrências
    total_ocorrencias = Ocorrencia.query.filter_by(camera_id=id).count()
    
    # Últimas 30 dias
    trinta_dias_atras = datetime.utcnow() - timedelta(days=30)
    ocorrencias_recentes = Ocorrencia.query.filter(
        Ocorrencia.camera_id == id,
        Ocorrencia.created_at >= trinta_dias_atras
    ).count()
    
    # Por categoria
    por_categoria = db.session.query(
        Ocorrencia.categoria,
        func.count(Ocorrencia.id)
    ).filter(
        Ocorrencia.camera_id == id
    ).group_by(Ocorrencia.categoria).all()
    
    # Últimas ocorrências detectadas
    ultimas_ocorrencias = Ocorrencia.query.filter_by(
        camera_id=id
    ).order_by(desc(Ocorrencia.created_at)).limit(10).all()
    
    # Calcular uptime (%)
    uptime = calcular_uptime(camera)
    
    return render_template('cameras/detalhes.html',
                         camera=camera,
                         total_ocorrencias=total_ocorrencias,
                         ocorrencias_recentes=ocorrencias_recentes,
                         por_categoria=por_categoria,
                         ultimas_ocorrencias=ultimas_ocorrencias,
                         uptime=uptime)

@cameras_bp.route('/adicionar', methods=['GET', 'POST'])
@login_required
@gestor_required
def adicionar():
    """Adicionar nova câmera"""
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            url_stream = request.form.get('url_stream')
            latitude = request.form.get('latitude', type=float)
            longitude = request.form.get('longitude', type=float)
            localizacao_descritiva = request.form.get('localizacao_descritiva')
            
            # Validações
            if not all([nome, url_stream, latitude, longitude]):
                flash('Preencha todos os campos obrigatórios.', 'warning')
                return redirect(request.url)
            
            # Testar conexão com câmera
            testar_conexao = request.form.get('testar_conexao', 'true') == 'true'
            
            if testar_conexao:
                status_teste = testar_camera(url_stream)
                if not status_teste['sucesso']:
                    flash(f'Erro ao conectar na câmera: {status_teste["mensagem"]}', 'danger')
                    return redirect(request.url)
            
            # Criar câmera
            camera = Camera(
                nome=nome,
                url_stream=url_stream,
                latitude=latitude,
                longitude=longitude,
                localizacao_descritiva=localizacao_descritiva,
                status='offline',
                ativa=True
            )
            
            db.session.add(camera)
            db.session.commit()
            
            flash(f'Câmera "{nome}" adicionada com sucesso!', 'success')
            return redirect(url_for('cameras.detalhes', id=camera.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao adicionar câmera: {str(e)}', 'danger')
            return redirect(request.url)
    
    return render_template('cameras/adicionar.html')

@cameras_bp.route('/<uuid:id>/editar', methods=['GET', 'POST'])
@login_required
@gestor_required
def editar(id):
    """Editar câmera"""
    camera = Camera.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            camera.nome = request.form.get('nome', camera.nome)
            camera.url_stream = request.form.get('url_stream', camera.url_stream)
            camera.latitude = request.form.get('latitude', type=float) or camera.latitude
            camera.longitude = request.form.get('longitude', type=float) or camera.longitude
            camera.localizacao_descritiva = request.form.get('localizacao_descritiva', camera.localizacao_descritiva)
            
            db.session.commit()
            
            flash('Câmera atualizada com sucesso!', 'success')
            return redirect(url_for('cameras.detalhes', id=id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
    
    return render_template('cameras/editar.html', camera=camera)

@cameras_bp.route('/<uuid:id>/deletar', methods=['POST'])
@login_required
@gestor_required
def deletar(id):
    """Deletar câmera"""
    camera = Camera.query.get_or_404(id)
    
    try:
        # Verificar se tem ocorrências associadas
        total_ocorrencias = Ocorrencia.query.filter_by(camera_id=id).count()
        
        if total_ocorrencias > 0:
            # Apenas desativar
            camera.ativa = False
            db.session.commit()
            flash(f'Câmera desativada (possui {total_ocorrencias} ocorrências associadas).', 'info')
        else:
            # Deletar permanentemente
            db.session.delete(camera)
            db.session.commit()
            flash('Câmera deletada com sucesso!', 'success')
        
        return redirect(url_for('cameras.lista'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar: {str(e)}', 'danger')
        return redirect(url_for('cameras.detalhes', id=id))

@cameras_bp.route('/<uuid:id>/status', methods=['POST'])
@login_required
@gestor_required
def alterar_status(id):
    """Alterar status da câmera (online/offline/manutenção)"""
    camera = Camera.query.get_or_404(id)
    
    try:
        novo_status = request.form.get('status')
        
        if novo_status not in ['online', 'offline', 'manutencao']:
            flash('Status inválido.', 'warning')
            return redirect(url_for('cameras.detalhes', id=id))
        
        camera.status = novo_status
        db.session.commit()
        
        flash(f'Status alterado para {novo_status}.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao alterar status: {str(e)}', 'danger')
    
    return redirect(url_for('cameras.detalhes', id=id))

@cameras_bp.route('/<uuid:id>/testar')
@login_required
@gestor_required
def testar(id):
    """Testar conexão com câmera"""
    camera = Camera.query.get_or_404(id)
    
    resultado = testar_camera(camera.url_stream)
    
    if resultado['sucesso']:
        # Atualizar status
        camera.status = 'online'
        camera.ultima_captura_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'mensagem': 'Câmera online e funcionando!',
            'status': 'online'
        })
    else:
        camera.status = 'offline'
        db.session.commit()
        
        return jsonify({
            'sucesso': False,
            'mensagem': resultado['mensagem'],
            'status': 'offline'
        }), 500


# ============================================================
# 📱 NOVOS ENDPOINTS - Sistema de Câmeras Móveis
# ============================================================

@cameras_bp.route('/upload', methods=['POST'])
@csrf.exempt  # Excluir da proteção CSRF (API pública para dispositivos móveis)
def upload_imagem():
    """
    Endpoint para receber imagens das câmeras móveis (celulares/tablets)
    
    Recebe:
        - device_id: ID único do dispositivo
        - timestamp: Data/hora da captura
        - latitude: Latitude da captura
        - longitude: Longitude da captura
        - image_base64: Imagem codificada em base64
    
    Processa:
        1. Salva a imagem
        2. Registra/atualiza câmera
        3. Envia para análise de IA
        4. Cria ocorrência automaticamente
        5. Notifica via WebSocket
    
    Retorna:
        JSON com status do processamento
    """
    try:
        current_app.logger.info("=" * 60)
        current_app.logger.info("📸 NOVA CAPTURA RECEBIDA!")
        current_app.logger.info("=" * 60)
        
        # 1. Validar dados recebidos
        dados = request.get_json()
        
        if not dados:
            current_app.logger.error("❌ Nenhum dado JSON recebido")
            return jsonify({
                "status": "error",
                "message": "Dados JSON inválidos"
            }), 400
        
        device_id = dados.get('device_id')
        timestamp_str = dados.get('timestamp')
        latitude = dados.get('latitude')
        longitude = dados.get('longitude')
        image_b64 = dados.get('image_base64')
        
        # Validações
        if not all([device_id, latitude, longitude, image_b64]):
            current_app.logger.error("❌ Campos obrigatórios faltando")
            return jsonify({
                "status": "error",
                "message": "Campos obrigatórios: device_id, latitude, longitude, image_base64"
            }), 400
        
        current_app.logger.info(f"📱 Device ID: {device_id}")
        current_app.logger.info(f"📍 Localização: {latitude}, {longitude}")
        current_app.logger.info(f"🖼️ Imagem: {len(image_b64)} caracteres em base64")
        
        # 2. Buscar ou criar câmera
        camera = Camera.query.filter_by(nome=f"Camera-{device_id}").first()
        
        if not camera:
            current_app.logger.info(f"📹 Registrando nova câmera: {device_id}")
            camera = Camera(
                nome=f"Camera-{device_id}",
                url_stream=f"mobile://{device_id}",
                latitude=latitude,
                longitude=longitude,
                localizacao_descritiva=f"Câmera Móvel - {device_id}",
                status='online',
                ativa=True
            )
            db.session.add(camera)
            db.session.flush()  # Obter ID da câmera
        else:
            current_app.logger.info(f"📹 Atualizando câmera existente: {camera.nome}")
            camera.status = 'online'
            camera.latitude = latitude
            camera.longitude = longitude
        
        camera.ultima_captura_at = datetime.utcnow()
        
        # 3. Salvar imagem
        try:
            image_data = base64.b64decode(image_b64)
            
            # Gerar nome único para a imagem
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"camera_{device_id}_{timestamp}_{uuid_lib.uuid4().hex[:8]}.jpg"
            
            # Caminho completo
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            ocorrencias_folder = os.path.join(upload_folder, 'ocorrencias')
            os.makedirs(ocorrencias_folder, exist_ok=True)
            
            filepath = os.path.join(ocorrencias_folder, filename)
            
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            size_mb = len(image_data) / (1024 * 1024)
            current_app.logger.info(f"💾 Imagem salva: {filepath} ({size_mb:.2f} MB)")
            
        except Exception as e:
            current_app.logger.error(f"❌ Erro ao salvar imagem: {e}")
            return jsonify({
                "status": "error",
                "message": f"Erro ao salvar imagem: {str(e)}"
            }), 500
        
        # 4. Análise com IA
        current_app.logger.info("🤖 Enviando para análise de IA...")
        ia_result = IAService.classificar_imagem(filepath)

        if not ia_result:
            current_app.logger.info("🚫 Nenhuma ocorrência detectada na imagem.")
            try:
                db.session.add(camera)
                db.session.commit()
            except Exception as commit_error:
                current_app.logger.warning(
                    f"⚠️ Falha ao salvar estado da câmera sem ocorrências: {commit_error}"
                )
                db.session.rollback()
            return jsonify({
                "status": "success",
                "message": "Sem ocorrências detectadas",
                "data": {
                    "ocorrencias": []
                },
                "timestamp": datetime.utcnow().isoformat()
            }), 200

        current_app.logger.info(f"✅ IA retornou {len(ia_result)} ocorrência(s)")
        
        # 5. Obter endereço completo
        try:
            geo_service = get_geo_service()
            endereco = geo_service.obter_endereco(latitude, longitude)
        except Exception as e:
            current_app.logger.warning(f"⚠️ Erro no geocoding: {e}")
            endereco = f"Lat: {latitude}, Lon: {longitude}"
        
        # 6. Criar ocorrência
        ocorrencias_criadas = []
        for det in ia_result:
            categoria = det.get('categoria', 'desconhecido')
            urgencia = det.get('urgencia', 'nao_urgente')
            descricao_ia = det.get('descricao', '')
            confidence = det.get('confidence', 0.0)

            ocorrencia = Ocorrencia(
                camera_id=camera.id,
                imagem_path=filepath,
                latitude=latitude,
                longitude=longitude,
                endereco_completo=endereco,
                categoria=categoria,
                urgencia=urgencia,
                status='pendente',
                descricao_ia=descricao_ia,
                confidence_score=confidence
            )

            db.session.add(ocorrencia)
            ocorrencias_criadas.append(ocorrencia)

        db.session.commit()

        current_app.logger.info(f"📝 {len(ocorrencias_criadas)} ocorrência(s) criada(s)")

        ocorrencias_payload = [
            {
                'id': str(ocorrencia.id),
                'ocorrencia_id': str(ocorrencia.id),
                'camera_id': str(camera.id),
                'categoria': ocorrencia.categoria,
                'urgencia': ocorrencia.urgencia,
                'confidence': ocorrencia.confidence_score,
                'endereco': endereco,
                'latitude': float(latitude),
                'longitude': float(longitude),
                'created_at': ocorrencia.created_at.isoformat(),
                'status': 'pendente',
            }
            for ocorrencia in ocorrencias_criadas
        ]

        # 7. Notificar via WebSocket (em lote para evitar duplicidades entre namespaces)
        try:
            payloads = [
                {
                    'id': str(ocorrencia.id),
                    'categoria': ocorrencia.categoria,
                    'urgencia': ocorrencia.urgencia,
                    'status': 'pendente',
                    'latitude': float(latitude),
                    'longitude': float(longitude),
                    'endereco': endereco,
                    'camera_nome': camera.nome,
                    'confidence': ocorrencia.confidence_score,
                    'created_at': ocorrencia.created_at.isoformat(),
                    'timestamp': datetime.utcnow().isoformat()
                }
                for ocorrencia in ocorrencias_criadas
            ]

            # Notificar painéis em ambos os namespaces apenas uma vez por lote
            socketio.emit(
                'nova_ocorrencia',
                payloads,
                namespace='/',
                broadcast=True
            )
            socketio.emit(
                'nova_ocorrencia',
                payloads,
                namespace='/dashboard',
                broadcast=True
            )

            socketio.emit('camera_update', {
                'camera_id': str(camera.id),
                'camera_nome': camera.nome,
                'status': 'online',
                'ultima_captura': datetime.utcnow().isoformat()
            }, namespace='/', broadcast=True)

            current_app.logger.info("📡 Notificações WebSocket enviadas")
        except Exception as e:
            current_app.logger.warning(f"⚠️ Erro ao enviar WebSocket: {e}")

        current_app.logger.info("=" * 60)
        current_app.logger.info("✅ PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        current_app.logger.info("=" * 60)
        
        # 8. Responder ao dispositivo
        return jsonify({
            "status": "success",
            "message": "Imagem processada com sucesso",
            "data": {
                "ocorrencias": ocorrencias_payload,
                "camera_id": str(camera.id)
            },
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ ERRO NO PROCESSAMENTO: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        
        return jsonify({
            "status": "error",
            "message": f"Erro no processamento: {str(e)}"
        }), 500


@cameras_bp.route('/capturas_recentes')
@login_required
@gestor_required
def capturas_recentes():
    """
    Retorna as últimas capturas de todas as câmeras
    Para exibir em tempo real na interface
    """
    try:
        # Últimas 50 ocorrências criadas por câmeras
        ocorrencias = db.session.query(
            Ocorrencia,
            Camera
        ).join(
            Camera, Ocorrencia.camera_id == Camera.id
        ).filter(
            Camera.url_stream.like('mobile://%')  # Apenas câmeras móveis
        ).order_by(
            desc(Ocorrencia.created_at)
        ).limit(50).all()
        
        capturas = []
        for ocorrencia, camera in ocorrencias:
            capturas.append({
                'id': str(ocorrencia.id),
                'camera_id': str(camera.id),
                'camera_nome': camera.nome,
                'categoria': ocorrencia.categoria,
                'urgencia': ocorrencia.urgencia,
                'latitude': float(ocorrencia.latitude),
                'longitude': float(ocorrencia.longitude),
                'endereco': ocorrencia.endereco_completo,
                'confidence': ocorrencia.confidence_score,
                'imagem_path': ocorrencia.imagem_path,
                'created_at': ocorrencia.created_at.isoformat()
            })
        
        return jsonify({
            'status': 'success',
            'capturas': capturas,
            'total': len(capturas)
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar capturas: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@cameras_bp.route('/estatisticas')
@login_required
@gestor_required
def estatisticas():
    """
    Retorna estatísticas das câmeras em tempo real
    """
    try:
        # Total de câmeras móveis
        total_cameras = Camera.query.filter(
            Camera.url_stream.like('mobile://%')
        ).count()
        
        # Câmeras online (última captura < 5 minutos)
        cinco_min_atras = datetime.utcnow() - timedelta(minutes=5)
        cameras_online = Camera.query.filter(
            Camera.url_stream.like('mobile://%'),
            Camera.ultima_captura_at >= cinco_min_atras
        ).count()
        
        # Total de capturas hoje
        hoje = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        capturas_hoje = db.session.query(Ocorrencia).join(Camera).filter(
            Camera.url_stream.like('mobile://%'),
            Ocorrencia.created_at >= hoje
        ).count()
        
        # Capturas por categoria (hoje)
        por_categoria = db.session.query(
            Ocorrencia.categoria,
            func.count(Ocorrencia.id)
        ).join(Camera).filter(
            Camera.url_stream.like('mobile://%'),
            Ocorrencia.created_at >= hoje
        ).group_by(Ocorrencia.categoria).all()
        
        return jsonify({
            'status': 'success',
            'total_cameras': total_cameras,
            'cameras_online': cameras_online,
            'cameras_offline': total_cameras - cameras_online,
            'capturas_hoje': capturas_hoje,
            'por_categoria': [
                {'categoria': cat, 'total': total}
                for cat, total in por_categoria
            ]
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar estatísticas: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@cameras_bp.route('/monitor')
@login_required
@gestor_required
def monitor():
    """
    Página de monitoramento em tempo real das câmeras
    Mostra capturas recentes e estatísticas
    """
    return render_template('cameras/monitor.html')


# ============================================================
# Funções auxiliares
# ============================================================

def testar_camera(url_stream):
    """
    Testa conexão com a câmera
    
    Returns:
        dict: {'sucesso': bool, 'mensagem': str}
    """
    try:
        # Tentar acessar URL da câmera (timeout 5s)
        response = requests.head(url_stream, timeout=5)
        
        if response.status_code == 200:
            return {'sucesso': True, 'mensagem': 'Conexão estabelecida'}
        else:
            return {
                'sucesso': False,
                'mensagem': f'Código HTTP {response.status_code}'
            }
            
    except requests.exceptions.Timeout:
        return {'sucesso': False, 'mensagem': 'Timeout ao conectar'}
    except requests.exceptions.ConnectionError:
        return {'sucesso': False, 'mensagem': 'Não foi possível conectar'}
    except Exception as e:
        return {'sucesso': False, 'mensagem': str(e)}


def calcular_uptime(camera):
    """
    Calcula uptime da câmera nos últimos 30 dias
    
    Args:
        camera: Objeto Camera
    
    Returns:
        float: Porcentagem de uptime (0-100)
    """
    # TODO: Implementar lógica real baseada em logs de status
    # Por enquanto, retorna estimativa baseada em última captura
    
    if not camera.ultima_captura_at:
        return 0.0
    
    diff = datetime.utcnow() - camera.ultima_captura_at
    horas_desde_ultima = diff.total_seconds() / 3600
    
    if horas_desde_ultima < 1:
        return 100.0
    elif horas_desde_ultima < 24:
        return 95.0
    elif horas_desde_ultima < 168:  # 7 dias
        return 70.0
    else:
        return 30.0