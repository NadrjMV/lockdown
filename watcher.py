import os
import time
import logging
import json
from config import ZM_CACHE_DIR, CLEANUP_INTERVAL_MINUTES, IA_MONITORING_FILE
from db import get_active_monitor_ids, get_latest_event
from processor import process_event, load_processed
import stats
from cleaner import run_cleanup

# Garante permissões corretas para o grupo
os.umask(0o002)

def start_daemon_watch():
    logging.info("🚀 IA Ligada - Modo Real-Time (Filtro de Alertas Ativo)")
    
    ZMMOIDS = get_active_monitor_ids()
    processed = load_processed()
    
    # --- PONTO DE CORTE PARA EVITAR FILA ANTIGA ---
    last_event_by_cam = {}
    for cam_id in ZMMOIDS:
        last_id, _ = get_latest_event(cam_id)
        if last_id:
            last_event_by_cam[cam_id] = last_id
            logging.info(f"📍 Cam {cam_id}: Monitorando a partir do ID {last_id}")

    last_cleanup_time = time.time()
    last_db_sync_time = 0
    last_year  = time.strftime("%Y")
    last_month = time.strftime("%m")

    try:
        while True:
            current_time = time.time()
            today_str = time.strftime("%Y-%m-%d")

            for cam_id in ZMMOIDS:
                new_id, start_time = get_latest_event(cam_id)
                
                # Só processa se o ID for maior que o registrado no início
                if new_id and new_id > last_event_by_cam.get(cam_id, 0):
                    event_date = start_time.strftime("%Y-%m-%d") if hasattr(start_time, 'strftime') else str(start_time)[:10]
                    
                    if event_date == today_str:
                        logging.info(f"🔔 Novo sinal detectado: Cam {cam_id}, Evento {new_id}")
                        stats.increment_total(event_date)
                        
                        # Delay para gravação no disco NTFS lento
                        time.sleep(2) 
                        process_event(cam_id, event_date, new_id, processed)
                    
                    # Atualiza o ponteiro para o próximo ciclo
                    last_event_by_cam[cam_id] = new_id

            # Sincroniza câmeras a cada 30s (ajustado para ser mais estável)
            if current_time - last_db_sync_time > 30:
                ZMMOIDS = get_active_monitor_ids()
                with open(IA_MONITORING_FILE, 'w', encoding='utf-8') as f:
                    json.dump(ZMMOIDS, f)
                last_db_sync_time = current_time

            # Limpeza automática conforme intervalo do config.py
            if current_time - last_cleanup_time > (CLEANUP_INTERVAL_MINUTES * 60):
                logging.info("⏰ Executando rotina de limpeza automática...")
                try:
                    run_cleanup()
                except Exception:
                    logging.exception("Erro na limpeza.")
                last_cleanup_time = current_time

            # Rollover de estatísticas mensais (essencial para o stats.py)
            now_month = time.strftime("%m")
            if now_month != last_month:
                stats.generate_monthly_summary(last_year, last_month)
                last_year, last_month = time.strftime("%Y"), now_month

            time.sleep(2)

    except KeyboardInterrupt:
        logging.info("Encerrando IA...")