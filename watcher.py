import os
import time
import re
import logging
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import ZM_CACHE_DIR, CLEANUP_INTERVAL_MINUTES, IA_MONITORING_FILE
from db import get_active_monitor_ids
from processor import process_event, load_processed
import stats
from cleaner import run_cleanup  # Importa a função de limpeza

# Define o umask global para que novos arquivos/pastas permitam escrita pelo grupo (664/775)
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

                # filtro para processar apenas data do dia
                today_str = time.strftime("%Y-%m-%d")
                if date_str != today_str:
                    # ignora os eventos de datas passadas
                    return

                if camera_id_str.isdigit() and re.match(r"\d{4}-\d{2}-\d{2}$", date_str) and event_id_str.isdigit():
                    cam_id = int(camera_id_str)

                    # Lógica Hot-Reload (mantida para resposta imediata a novas câmeras)
                    if cam_id not in self.ZMMOIDS:
                        logging.info(f"🔎 ID {cam_id} desconhecido. Verificando DB...")
                        current_active_ids = get_active_monitor_ids()
                        if cam_id in current_active_ids:
                            self.ZMMOIDS = current_active_ids 
                            logging.info(f"✅ Nova câmera {cam_id} adicionada dinamicamente!")

                    if cam_id in self.ZMMOIDS:
                        logging.info(f"✔️  Novo evento detectado: Cam {cam_id}, Evento {event_id_str}")
                        stats.increment_total(date_str)
                        time.sleep(5)
                        process_event(cam_id, date_str, int(event_id_str), self.processed_events)
                    else:
                        logging.info(f"Ignorando câmera não configurada: {cam_id}")
        except Exception:
            logging.exception(f"Erro ao processar o caminho: {event.src_path}")

def start_daemon_watch():
    ZMMOIDS = get_active_monitor_ids()
    if not ZMMOIDS:
        logging.warning("Nenhuma câmera ativa no DB.")

    processed = load_processed()
    # Aponta direto para a pasta Events_ZM no novo volume
    base      = ZM_CACHE_DIR 

    observer = Observer()
    handler  = NewEventHandler(processed, base, ZMMOIDS)
    observer.schedule(handler, base, recursive=True)
    observer.start()
    logging.info(f"✅ Monitoramento iniciado em: {base}. IDs: {ZMMOIDS}")

    counter    = 0
    last_year  = time.strftime("%Y")
    last_month = time.strftime("%m")
    
    # --- Marca o tempo da última limpeza ---
    last_cleanup_time = time.time() 

    try:
        while True:
            time.sleep(1)
            counter += 1

            # 1. Rollover de mês (Stats)
            now_year  = time.strftime("%Y")
            now_month = time.strftime("%m")
            if now_month != last_month:
                stats.generate_monthly_summary(last_year, last_month)
                last_year, last_month = now_year, now_month

            # 2. VERIFICAÇÃO DE LIMPEZA
            time_since_cleanup = time.time() - last_cleanup_time
            interval_seconds = CLEANUP_INTERVAL_MINUTES * 60 

            if time_since_cleanup > interval_seconds:
                logging.info(f"⏰ Intervalo de {CLEANUP_INTERVAL_MINUTES} min atingido. Iniciando limpeza...")
                try:
                    run_cleanup()
                except Exception:
                    logging.exception("Erro ao executar limpeza automática.")
                
                last_cleanup_time = time.time()

            # 3. ATUALIZAÇÃO DA LISTA DE MONITORAMENTO (A cada 20 segundos)
            if counter >= 20:
                try:
                    # Sincroniza com o Banco de Dados para detectar adições e REMOÇÕES
                    current_ids = get_active_monitor_ids()
                    handler.ZMMOIDS = current_ids # Atualiza o handler na memória
                    
                    # Salva no arquivo JSON para o frontend
                    with open(IA_MONITORING_FILE, 'w', encoding='utf-8') as f:
                        json.dump(current_ids, f)
                    
                    logging.info(f"🔄 Lista de câmeras atualizada: {current_ids}")
                except Exception:
                    logging.exception("Erro ao atualizar lista de monitoramento via loop.")
                
                counter = 0

    except KeyboardInterrupt:
        observer.stop()
    observer.join()