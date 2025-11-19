from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc, or_
from app import db, socketio
from app.models import Ocorrencia, Camera, OrdemServico
from app.services.image_service import ImageService
from app.services.ia_service import IAService
from app.services.geo_service import get_geo_service # type: ignore
from app.utils.decorators import gestor_required
from datetime import datetime
import os

ocorrencias_bp = Blueprint('ocorrencias', __name__)

@ocorrencias_bp.route('/')
@ocorrencias_bp.route('/lista')
@login_required
def lista():
    """Lista todas as ocorrências com filtros"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Filtros
    status = request.args.get('status')
    categoria = request.args.get('categoria')
    urgencia = request.args.get('urgencia')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    busca = request.args.get('busca')
    
    # Query base
    query = Ocorrencia.query
    
    # Aplicar filtros
    if status:
        query = query.filter(Ocorrencia.status == status)
    
    if categoria:
        query = query.filter(Ocorrencia.categoria == categoria)
    
    if urgencia:
        query = query.filter(Ocorrencia.urgencia == urgencia)
    
    if data_inicio:
        data_inicio_dt = datetime.fromisoformat(data_inicio)
        query = query.filter(Ocorrencia.created_at >= data_inicio_dt)
    
    if data_fim:
        data_fim_dt = datetime.fromisoformat(data_fim)
        query = query.filter(Ocorrencia.created_at <= data_fim_dt)
    
    if busca:
        query = query.filter(
            or_(
                Ocorrencia.endereco_completo.ilike(f'%{busca}%'),
                Ocorrencia.descricao_ia.ilike(f'%{busca}%')
            )
        )
    
    # Ordenar por data (mais recentes primeiro)
    query = query.order_by(desc(Ocorrencia.created_at))
    
    # Paginar
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    ocorrencias = pagination.items
    
    return render_template('ocorrencias/lista.html',
                         ocorrencias=ocorrencias,
                         pagination=pagination)

@ocorrencias_bp.route('/<uuid:id>')
@login_required
def detalhes(id):
    """Detalhes de uma ocorrência específica"""
    ocorrencia = Ocorrencia.query.get_or_404(id)
    
    # Verificar se já tem OS associada
    os_associada = OrdemServico.query.filter_by(ocorrencia_id=id).first()
    
    return render_template('ocorrencias/detalhes.html',
                         ocorrencia=ocorrencia,
                         os_associada=os_associada)

@ocorrencias_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@gestor_required
def upload():
    """Upload manual de ocorrência"""
    if request.method == 'POST':
        try:
            # Validar arquivo
            if 'imagem' not in request.files:
                flash('Nenhuma imagem foi enviada.', 'warning')
                return redirect(request.url)
            
            file = request.files['imagem']
            
            if file.filename == '':
                flash('Nenhuma imagem selecionada.', 'warning')
                return redirect(request.url)
            
            if not ImageService.allowed_file(file.filename):
                flash('Tipo de arquivo não permitido. Use JPG, JPEG ou PNG.', 'warning')
                return redirect(request.url)
            
            # Obter dados do formulário
            latitude = request.form.get('latitude', type=float)
            longitude = request.form.get('longitude', type=float)
            categoria_manual = request.form.get('categoria')
            urgencia_manual = request.form.get('urgencia')
            descricao_manual = request.form.get('descricao')
            
            # Processar imagem
            resultado = ImageService.processar_upload(
                file,
                latitude=latitude,
                longitude=longitude
            )
            
            # Classificar com IA (se não fornecido manualmente)
            if not categoria_manual:
                deteccoes = IAService.classificar_imagem(resultado['imagem_path'])

                if not deteccoes:
                    flash('Nenhuma ocorrência detectada na imagem.', 'warning')
                    return redirect(url_for('ocorrencias.upload'))
            else:
                deteccoes = [{
                    'categoria': categoria_manual,
                    'urgencia': urgencia_manual or 'nao_urgente',
                    'descricao': descricao_manual or '',
                    'confidence': 1.0,
                }]
            
            # Obter endereço
            geo_service = get_geo_service()
            endereco = geo_service.obter_endereco(
                resultado['latitude'],
                resultado['longitude']
            )
            
            # Criar ocorrências
            ocorrencias_criadas = []
            for det in deteccoes:
                ocorrencia = Ocorrencia(
                    imagem_path=resultado['imagem_path'],
                    imagem_miniatura_path=resultado['miniatura_path'],
                    latitude=resultado['latitude'],
                    longitude=resultado['longitude'],
                    endereco_completo=endereco,
                    categoria=det.get('categoria', 'desconhecido'),
                    urgencia=det.get('urgencia', 'nao_urgente'),
                    status='pendente',
                    descricao_ia=det.get('descricao'),
                    confidence_score=det.get('confidence'),
                    metadados_exif=resultado['metadados']
                )
                db.session.add(ocorrencia)
                ocorrencias_criadas.append(ocorrencia)

            db.session.commit()

            # Emitir eventos WebSocket em lote para evitar duplicidade
            payloads = [
                {
                    'id': str(ocorrencia.id),
                    'categoria': ocorrencia.categoria,
                    'urgencia': ocorrencia.urgencia,
                    'status': ocorrencia.status,
                    'latitude': float(ocorrencia.latitude),
                    'longitude': float(ocorrencia.longitude),
                    'endereco': ocorrencia.endereco_completo,
                    'created_at': ocorrencia.created_at.isoformat()
                }
                for ocorrencia in ocorrencias_criadas
            ]

            socketio.emit('nova_ocorrencia', payloads, namespace='/dashboard', broadcast=True)
            socketio.emit('nova_ocorrencia', payloads, namespace='/', broadcast=True)

            if len(ocorrencias_criadas) == 1:
                flash('Ocorrência registrada com sucesso!', 'success')
                return redirect(url_for('ocorrencias.detalhes', id=ocorrencias_criadas[0].id))

            flash(f"{len(ocorrencias_criadas)} ocorrências registradas com sucesso!", 'success')
            return redirect(url_for('ocorrencias.lista'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao processar ocorrência: {str(e)}', 'danger')
            return redirect(request.url)
    
    return render_template('ocorrencias/upload.html')

@ocorrencias_bp.route('/<uuid:id>/editar', methods=['GET', 'POST'])
@login_required
@gestor_required
def editar(id):
    """Editar ocorrência"""
    ocorrencia = Ocorrencia.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            ocorrencia.categoria = request.form.get('categoria', ocorrencia.categoria)
            ocorrencia.urgencia = request.form.get('urgencia', ocorrencia.urgencia)
            ocorrencia.descricao_ia = request.form.get('descricao', ocorrencia.descricao_ia)
            
            db.session.commit()
            
            flash('Ocorrência atualizada com sucesso!', 'success')
            return redirect(url_for('ocorrencias.detalhes', id=id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
    
    return render_template('ocorrencias/editar.html', ocorrencia=ocorrencia)

@ocorrencias_bp.route('/<uuid:id>/deletar', methods=['POST'])
@login_required
@gestor_required
def deletar(id):
    """Deletar ocorrência"""
    ocorrencia = Ocorrencia.query.get_or_404(id)
    
    try:
        # Verificar se tem OS associada
        if ocorrencia.ordem_servico:
            flash('Não é possível deletar ocorrência com Ordem de Serviço associada.', 'warning')
            return redirect(url_for('ocorrencias.detalhes', id=id))
        
        # Deletar arquivos
        if os.path.exists(ocorrencia.imagem_path):
            os.remove(ocorrencia.imagem_path)
        
        if os.path.exists(ocorrencia.imagem_miniatura_path):
            os.remove(ocorrencia.imagem_miniatura_path)
        
        db.session.delete(ocorrencia)
        db.session.commit()
        
        flash('Ocorrência deletada com sucesso!', 'success')
        return redirect(url_for('ocorrencias.lista'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar: {str(e)}', 'danger')
        return redirect(url_for('ocorrencias.detalhes', id=id))

@ocorrencias_bp.route('/mapa')
@login_required
def mapa():
    """Visualização em mapa"""
    return render_template('ocorrencias/mapa.html')

@ocorrencias_bp.route('/estatisticas')
@login_required
@gestor_required
def estatisticas():
    """Estatísticas gerais de ocorrências"""
    from sqlalchemy import func
    
    # Totais por categoria
    por_categoria = db.session.query(
        Ocorrencia.categoria,
        func.count(Ocorrencia.id)
    ).group_by(Ocorrencia.categoria).all()
    
    # Totais por urgência
    por_urgencia = db.session.query(
        Ocorrencia.urgencia,
        func.count(Ocorrencia.id)
    ).group_by(Ocorrencia.urgencia).all()
    
    # Totais por status
    por_status = db.session.query(
        Ocorrencia.status,
        func.count(Ocorrencia.id)
    ).group_by(Ocorrencia.status).all()
    
    return render_template('ocorrencias/estatisticas.html',
                         por_categoria=por_categoria,
                         por_urgencia=por_urgencia,
                         por_status=por_status)


@ocorrencias_bp.route('/api/mapa/pontos')
@login_required
def mapa_pontos():
    """Retorna as ocorrências com dados completos para exibição no mapa"""
    categoria = request.args.get('categoria')
    urgencia = request.args.get('urgencia')
    status = request.args.get('status')

    query = Ocorrencia.query

    if categoria:
        query = query.filter(Ocorrencia.categoria == categoria)
    if urgencia:
        query = query.filter(Ocorrencia.urgencia == urgencia)
    if status:
        query = query.filter(Ocorrencia.status == status)

    ocorrencias = query.all()
    return jsonify([o.to_dict() for o in ocorrencias])
