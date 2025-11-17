from flask import Flask, request, jsonify
import subprocess
import os
import uuid
import tempfile
from pathlib import Path

app = Flask(__name__)

# Configuración
TEMP_DIR = tempfile.gettempdir()
MAX_VIDEO_SIZE_GB = 5  # Límite de tamaño

@app.route('/health', methods=['GET'])
def health():
    """Verifica que la API está funcionando"""
    return jsonify({'status': 'ok', 'service': 'video-downloader'}), 200

@app.route('/download', methods=['POST'])
def download_video():
    """
    Descarga un vídeo de YouTube
    
    JSON esperado:
    {
        "video_url": "https://www.youtube.com/watch?v=XXXXX",
        "quality": "best"  (opcional: best, 720, 480, etc.)
    }
    
    Respuesta:
    {
        "job_id": "uuid",
        "status": "success",
        "filename": "video-name.mp4",
        "file_path": "/tmp/...",
        "file_size_mb": 123.45
    }
    """
    try:
        data = request.json
        video_url = data.get('video_url')
        quality = data.get('quality', 'best')
        
        # Validaciones
        if not video_url:
            return jsonify({'error': 'Falta parámetro: video_url'}), 400
        
        if not isinstance(video_url, str) or 'youtube' not in video_url.lower():
            return jsonify({'error': 'URL debe ser de YouTube'}), 400
        
        # ID único para este descarga
        job_id = str(uuid.uuid4())
        output_dir = os.path.join(TEMP_DIR, f'yt-{job_id}')
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"[{job_id}] Iniciando descarga desde: {video_url}")
        print(f"[{job_id}] Calidad: {quality}")
        print(f"[{job_id}] Directorio de salida: {output_dir}")
        
        # Comando yt-dlp
        cmd = [
            'yt-dlp',
            video_url,
            '-o', os.path.join(output_dir, '%(title)s.%(ext)s'),
            '--no-warnings',
            '--quiet'
        ]
        
        # Agregar opción de calidad si no es 'best'
        if quality != 'best':
            cmd.extend([
                '-f', f'bestvideo[height<={quality}]+bestaudio/best'
            ])
        
        # Ejecuta descarga
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        
        if result.returncode != 0:
            error_msg = result.stderr or "Error desconocido"
            print(f"[{job_id}] Error: {error_msg}")
            return jsonify({
                'error': f'Error descargando vídeo: {error_msg}',
                'job_id': job_id
            }), 500
        
        # Busca el archivo descargado
        files = os.listdir(output_dir)
        if not files:
            return jsonify({
                'error': 'No se descargó ningún archivo',
                'job_id': job_id
            }), 500
        
        filename = files[0]
        file_path = os.path.join(output_dir, filename)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        # Verifica límite de tamaño
        if file_size_mb > MAX_VIDEO_SIZE_GB * 1024:
            os.remove(file_path)
            return jsonify({
                'error': f'Archivo demasiado grande: {file_size_mb:.2f} MB (límite: {MAX_VIDEO_SIZE_GB * 1024} MB)',
                'job_id': job_id
            }), 413
        
        print(f"[{job_id}] ✅ Descarga completada")
        print(f"[{job_id}] Archivo: {filename} ({file_size_mb:.2f} MB)")
        
        return jsonify({
            'job_id': job_id,
            'status': 'success',
            'filename': filename,
            'file_path': file_path,
            'file_size_mb': round(file_size_mb, 2)
        }), 200
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout: descarga tardó demasiado (>1 hora)'}), 504
    except Exception as e:
        print(f"Error inesperado: {str(e)}")
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/file-info/<job_id>', methods=['GET'])
def get_file_info(job_id):
    """Obtiene info de un archivo descargado"""
    try:
        output_dir = os.path.join(TEMP_DIR, f'yt-{job_id}')
        
        if not os.path.exists(output_dir):
            return jsonify({'error': 'Job ID no encontrado'}), 404
        
        files = os.listdir(output_dir)
        if not files:
            return jsonify({'error': 'No hay archivos para este job'}), 404
        
        filename = files[0]
        file_path = os.path.join(output_dir, filename)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        return jsonify({
            'job_id': job_id,
            'filename': filename,
            'file_path': file_path,
            'file_size_mb': round(file_size_mb, 2)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint no encontrado'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Error interno del servidor'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
