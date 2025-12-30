import os
import time
import re
import logging
import json
from datetime import datetime, timedelta
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import ZM_CACHE_DIR, CLEANUP_INTERVAL_MINUTES, IA_MONITORING_FILE, MAX_EVENT_AGE_MINUTES
from db import get_active_monitor_ids, get_event_data
from processor import process_event, load_processed
import stats
from cleaner import run_cleanup 

# Permissões 775/664 para o Lockdown poder renomear/editar
os.umask(0o002)

class NewEventHandler(FileSystemEventHandler):
    def __init__(self, processed_events, base, zm_monitor_ids):
        self.processed_events = processed_events
        self.base             = base
        self.ZMMOIDS          = zm_monitor_ids 

    def on_created(self, event):
        if not event.is_directory:
            return

        try:
            rel_path = os.path.relpath(event.src_path, self.base)
            parts = rel_path.split(os.sep)

            if len(parts) == 3:
                camera_id_str, date_str, event_id_str = parts
                
                # Filtro de Hoje (Formato ZM: YYYY-MM-DD)
                today_zm = time.strftime("%Y-%m-%d")
                if date_str != today_zm:
                    return

                # TRAVA DE ATRASO: Ignora backlog se for mais velho que o limite
                event_id = int(event_id_str)
                start_time = get_event_data(event_id)
                
                if start_time:
                    age = datetime.now() - start_time
                    if age > timedelta(minutes=MAX_EVENT_AGE_MINUTES):
                        return

                cam_id = int(camera_id_str)
                if cam_id not in self.ZMMOIDS:
                    current_active_ids = get_active_monitor_ids()
                    if cam_id in current_active_ids:
                        self.ZMMOIDS = current_active_ids 

                if cam_id in self.ZMMOIDS:
                    logging.info(f"✔️ Novo evento detectado: Cam {cam_id}, Evento {event_id_str}")
                    stats.increment_total(date_str)
                    time.sleep(2) 
                    process_event(cam_id, date_str, event_id, self.processed_events, start_time)
        except Exception:
            logging.exception(f"Erro ao processar: {event.src_path}")

def start_daemon_watch():
    ZMMOIDS = get_active_monitor_ids()
    processed = load_processed()
    base = ZM_CACHE_DIR 

    observer = Observer()
    handler  = NewEventHandler(processed, base, ZMMOIDS)
    observer.schedule(handler, base, recursive=True)
    observer.start()
    logging.info(f"✅ Monitoramento iniciado em: {base}. Max age: {MAX_EVENT_AGE_MINUTES}min")

    counter    = 0
    last_year  = time.strftime("%Y")
    last_month = time.strftime("%m")
    last_cleanup_time = time.time() 

    try:
        while True:
            time.sleep(1)
            counter += 1

            # 1. Rollover de mês (Stats) - RECUPERADO
            now_year  = time.strftime("%Y")
            now_month = time.strftime("%m")
            if now_month != last_month:
                stats.generate_monthly_summary(last_year, last_month)
                last_year, last_month = now_year, now_month

            # 2. Limpeza automática
            if (time.time() - last_cleanup_time) > (CLEANUP_INTERVAL_MINUTES * 60):
                logging.info(f"⏰ Iniciando limpeza automática...")
                try:
                    run_cleanup()
                except Exception:
                    logging.exception("Erro na limpeza.")
                last_cleanup_time = time.time()

            # 3. Atualização para o Lockdown e log visual
            if counter >= 20:
                try:
                    current_ids = get_active_monitor_ids()
                    handler.ZMMOIDS = current_ids 
                    with open(IA_MONITORING_FILE, 'w', encoding='utf-8') as f:
                        json.dump(current_ids, f)
                    logging.info(f"⏳ Aguardando novos eventos... Monitorando: {current_ids}")
                except Exception:
                    logging.exception("Erro ao atualizar monitoramento.")
                counter = 0

    except KeyboardInterrupt:
        observer.stop()
    observer.join()