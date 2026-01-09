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
from stats import _load_stats 
from db import get_camera_groups 

# --- Configuração Inicial ---
app = FastAPI(
    title="Sentinel AI Dashboard API",
    description="API para servir dados de eventos de câmera processados.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --- Modelos de Dados ---
from pydantic import BaseModel

class Event(BaseModel):
    data_execucao: str
    camera: int
    evento: int
    is_critical: bool
    grupo: List[int]
    resultado: str
    objetos_detectados: List[str]
    log_filename: str 
    path_evento: str 

# --- Funções Auxiliares ---

def find_event_log_files(log_dir: str):
    """Busca logs no padrão da imagem: detections_log__ID_..."""
    events = []
    if not os.path.isdir(log_dir):
        return events

    for filename in os.listdir(log_dir):
        # Captura o padrão exato com os underscores da imagem
        if filename.startswith("detections_log__ID_") and filename.endswith(".json"):
            filepath = os.path.join(log_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['log_filename'] = filename
                    data['path_evento'] = os.path.join(f"ID_{data['camera']}", str(data['evento']))
                    events.append(data)
            except Exception as e:
                log.error(f"Erro ao ler log {filename}: {e}")
    return events

# --- Endpoints da API ---

@app.get("/api/status")
def get_status():
    return {"status": "ok", "message": "Sentinel AI API is running."}

@app.get("/api/stats/{year}/{month}", response_model=Dict)
def get_monthly_stats(year: str, month: str):
    month_num = str(int(month))
    summary_path = os.path.join(OUTPUT_DIR, 'Stats', year, month_num, f"{year}_{month_num}_summary.json")
    
    if not os.path.exists(summary_path):
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
        log.error(f"Erro ao ler estatísticas: {e}")
        raise HTTPException(status_code=500, detail="Could not read stats file.")

@app.get("/api/events", response_model=List[Event])
def get_events(event_date: date, camera_id: Optional[int] = None):
    date_str = event_date.strftime("%d-%m-%Y")
    base_log_dir = os.path.join(OUTPUT_DIR, date_str)
    all_events = []

    if camera_id:
        cam_log_dir = os.path.join(base_log_dir, f"ID_{camera_id}")
        all_events.extend(find_event_log_files(cam_log_dir))
    else:
        if os.path.isdir(base_log_dir):
            for cam_folder in os.listdir(base_log_dir):
                if cam_folder.startswith("ID_"):
                    full_cam_path = os.path.join(base_log_dir, cam_folder)
                    all_events.extend(find_event_log_files(full_cam_path))

    all_events.sort(key=lambda x: x['data_execucao'], reverse=True)
    return all_events

@app.get("/images/{camera_id}/{event_id}/{image_filename}")
async def get_image(camera_id: int, event_id: int, image_filename: str):
    image_path = os.path.join(OUTPUT_DIR, f"ID_{camera_id}", str(event_id), image_filename)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path)