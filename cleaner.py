import os
import time
import logging
import shutil
import subprocess
from datetime import datetime, timedelta

from config import OUTPUT_DIR, LOGS_GERAIS_DIR, ZM_CACHE_DIR, CLEANUP_RETENTION_DAYS, JSONErrorHandler 

def run_cleanup():
    RETENTION_DAYS = CLEANUP_RETENTION_DAYS
    DELETE_TIME_SECONDS = time.time() - (RETENTION_DAYS * 86400)
    DELETE_DATE = datetime.now() - timedelta(days=RETENTION_DAYS)

    logging.info(f"Iniciando rotina de limpeza. Limite: {RETENTION_DAYS} dias ({DELETE_DATE.strftime('%d-%m-%Y')}).")

    # --- 1. Limpeza de Logs Reais (Script_imagens) ---
    logging.info("--> 1/4: Limpando logs diários em Script_imagens.")
    if os.path.exists(OUTPUT_DIR):
        for folder_name in os.listdir(OUTPUT_DIR):
            daily_path = os.path.join(OUTPUT_DIR, folder_name)
            if not os.path.isdir(daily_path) or folder_name in ('Stats', 'processed_events.txt'):
                 continue
            try:
                folder_date = datetime.strptime(folder_name, "%d-%m-%Y")
                if folder_date.date() < DELETE_DATE.date():
                    logging.warning(f"🧹 Removendo pasta de log real: {daily_path}")
                    subprocess.run(["sudo", "rm", "-rf", daily_path], check=False)
            except ValueError: pass

    # --- 2. Limpeza do Histórico Geral (Logs_Gerais_IA) ---
    logging.info("--> 2/4: Limpando histórico total em Logs_Gerais_IA.")
    if os.path.exists(LOGS_GERAIS_DIR):
        for folder_name in os.listdir(LOGS_GERAIS_DIR):
            daily_path = os.path.join(LOGS_GERAIS_DIR, folder_name)
            if not os.path.isdir(daily_path) or folder_name == "Analise_Temporaria":
                continue
            try:
                folder_date = datetime.strptime(folder_name, "%d-%m-%Y")
                if folder_date.date() < DELETE_DATE.date():
                    logging.warning(f"🧹 Removendo pasta de histórico: {daily_path}")
                    subprocess.run(["sudo", "rm", "-rf", daily_path], check=False)
            except ValueError: pass

    # --- 3. Limpeza das Pastas de Imagens (ID_XXX/EVENTO_ID) ---
    logging.info("--> 3/4: Limpando pastas de imagens de eventos antigos.")
    if os.path.exists(OUTPUT_DIR):
        for cam_folder in os.listdir(OUTPUT_DIR):
            if not cam_folder.startswith('ID_'): continue
            cam_path = os.path.join(OUTPUT_DIR, cam_folder)
            for event_id in os.listdir(cam_path):
                event_path = os.path.join(cam_path, event_id)
                if os.path.isdir(event_path):
                    try:
                        if os.path.getmtime(event_path) < DELETE_TIME_SECONDS:
                            logging.warning(f"🧹 Removendo evento crítico antigo: {event_path}")
                            subprocess.run(["sudo", "rm", "-rf", event_path], check=False)
                    except: pass

    # --- 4. Limpeza do Cache do ZoneMinder ---
    logging.info("--> 4/4: Limpando cache original do ZoneMinder.")
    if os.path.isdir(ZM_CACHE_DIR):
        for cam_id in os.listdir(ZM_CACHE_DIR):
            cam_path = os.path.join(ZM_CACHE_DIR, cam_id)
            if not os.path.isdir(cam_path) or not cam_id.isdigit(): continue
            for date_folder in os.listdir(cam_path):
                date_path = os.path.join(cam_path, date_folder)
                try:
                    folder_date = datetime.strptime(date_folder, "%Y-%m-%d")
                    if folder_date.date() < DELETE_DATE.date():
                        logging.warning(f"🧹 Removendo cache ZM: {date_path}")
                        subprocess.run(["sudo", "rm", "-rf", date_path], check=False)
                except ValueError: continue

    logging.info("Rotina de limpeza concluída.")

if __name__ == "__main__":
    logger = logging.getLogger()
    if not any(isinstance(h, JSONErrorHandler) for h in logger.handlers):
         logger.addHandler(JSONErrorHandler())
    try:
        run_cleanup()
    except Exception:
        logging.exception("Erro fatal na execução da rotina de limpeza.")