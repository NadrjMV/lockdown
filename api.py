import os
import json
import logging
from datetime import date
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Importa as configurações dos scripts existentes
from config import OUTPUT_DIR, ZM_CACHE_DIR
from stats import _load_stats # Importa a função interna para reuso
from db import get_camera_groups # Reutiliza a função de busca de grupos

# --- Configuração Inicial ---
app = FastAPI(
    title="Sentinel AI Dashboard API",
    description="API para servir dados de eventos de câmera processados.",
    version="1.0.0"
)

# Configuração do CORS para permitir que o frontend acesse a API
# Em um ambiente de produção, restrinja para o domínio do site.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite todas as origens por enquanto
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --- Modelos de Dados (para garantir respostas consistentes) ---
from pydantic import BaseModel

class Event(BaseModel):
    data_execucao: str
    camera: int
    evento: int
    frames_analisados: int
    grupo: List[str]
    resultado: str
    objetos_detectados: List[str]
    log_filename: str # Para referência futura
    path_evento: str # Caminho para a pasta do evento original

# --- Funções Auxiliares ---

def find_event_log_files(log_dir: str):
    """Encontra e parseia todos os arquivos de log de detecção em um diretório."""
    events = []
    
    print(f"--- API está buscando logs na pasta: {log_dir}")
    
    if not os.path.isdir(log_dir):
        # AQUI ESTAVA O ERRO DE INDENTAÇÃO
        print(f"--- AVISO: A pasta acima não existe ou não é um diretório.")
        return events

    for filename in os.listdir(log_dir):
        if filename.startswith("detections_log_") and filename.endswith(".json"):
            print(f"--- SUCESSO: Encontrado o arquivo de log: {filename}")
            filepath = os.path.join(log_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['log_filename'] = filename
                    data['path_evento'] = os.path.join(f"ID_{data['camera']}", str(data['evento']))
                    events.append(data)
            except Exception as e:
                log.error(f"Falha ao ler o log {filepath}: {e}")
    return events

# --- Endpoints da API ---

@app.get("/api/status")
def get_status():
    """Endpoint simples para verificar se a API está online."""
    return {"status": "ok", "message": "Sentinel AI API is running."}

@app.get("/api/stats/{year}/{month}", response_model=Dict)
def get_monthly_stats(year: str, month: str):
    """Retorna as estatísticas consolidadas para um dado mês/ano."""
    month_num = str(int(month))
    summary_path = os.path.join(OUTPUT_DIR, 'Stats', year, month_num, f"{year}_{month_num}_summary.json")
    
    if not os.path.exists(summary_path):
        # Se o resumo não existir, calcula na hora (fallback)
        total = 0
        with_det = 0
        month_dir = os.path.join(OUTPUT_DIR, 'Stats', year, month_num)
        if os.path.isdir(month_dir):
             for day in os.listdir(month_dir):
                stat_file = os.path.join(month_dir, day, 'events_stats.json')
                if os.path.isfile(stat_file):
                    data = _load_stats(stat_file)
                    total  += data.get('total', 0)
                    with_det += data.get('with_detections', 0)
        return {"total_events": total, "with_detections": with_det}

    try:
        stats = _load_stats(summary_path)
        return stats
    except Exception as e:
        log.error(f"Erro ao ler estatísticas de {summary_path}: {e}")
        raise HTTPException(status_code=500, detail="Could not read stats file.")


@app.get("/api/events", response_model=List[Event])
def get_events(
    event_date: date,
    camera_id: Optional[int] = None
):
    """
    Retorna uma lista de eventos para uma data específica.
    Pode ser filtrado por camera_id.
    """
    date_str = event_date.strftime("%d-%m-%Y")
    
    # O processor.py salva os logs em pastas diárias dentro de pastas de câmera a partir da raiz
    # Ex: /var/www/html/Script_imagens/28-07-2025/ID_11/detections_log_...
    
    base_log_dir = os.path.join(OUTPUT_DIR, date_str)
    all_events = []

    if camera_id:
        # Se uma câmera foi especificada, olhe apenas na pasta dela
        cam_log_dir = os.path.join(base_log_dir, f"ID_{camera_id}")
        all_events.extend(find_event_log_files(cam_log_dir))
    else:
        # Se não, itere sobre todas as pastas de câmera do dia
        if os.path.isdir(base_log_dir):
            for cam_folder in os.listdir(base_log_dir):
                if cam_folder.startswith("ID_"):
                    full_cam_path = os.path.join(base_log_dir, cam_folder)
                    all_events.extend(find_event_log_files(full_cam_path))

    # Ordena os eventos pelo mais recente primeiro, baseado no nome do arquivo de log
    all_events.sort(key=lambda x: x['data_execucao'], reverse=True)
    
    return all_events

@app.get("/images/{camera_id}/{event_id}/{image_filename}")
async def get_image(camera_id: int, event_id: int, image_filename: str):
    """Serve um arquivo de imagem de um evento específico."""
    # O caminho para as imagens salvas pelo deepstack.py está em OUTPUT_DIR/ID_camera/evento/arquivo.jpg
    image_path = os.path.join(OUTPUT_DIR, f"ID_{camera_id}", str(event_id), image_filename)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path)