import os
import time
import logging
import shutil
import subprocess
from datetime import datetime, timedelta

from config import OUTPUT_DIR, LOGS_GERAIS_DIR, ZM_CACHE_DIR, CLEANUP_RETENTION_DAYS, JSONErrorHandler 

def run_cleanup():
    """
    Função principal da limpeza. Atua em Script_imagens, Logs_Gerais_IA e Cache ZM.
    Apaga arquivos/pastas mais antigos que o limite definido.
    """

    RETENTION_DAYS = CLEANUP_RETENTION_DAYS
    DELETE_TIME_SECONDS = time.time() - (RETENTION_DAYS * 86400)
    DELETE_DATE = datetime.now() - timedelta(days=RETENTION_DAYS)

    logging.info(f"Iniciando rotina de limpeza. Apagando dados mais antigos do que {RETENTION_DAYS} dias ({DELETE_DATE.strftime('%d-%m-%Y %H:%M:%S')}).")

    # --- 1. Limpeza do OUTPUT_DIR (Logs Reais e Imagens Críticas) ---
    logging.info("--> 1/4: Limpando logs reais em Script_imagens (pastas de data).")
    if os.path.exists(OUTPUT_DIR):
        for daily_folder_name in os.listdir(OUTPUT_DIR):
            daily_path = os.path.join(OUTPUT_DIR, daily_folder_name)
            
            if not os.path.isdir(daily_path) or daily_folder_name in ('Stats', 'processed_events.txt'):
                 continue

            try:
                folder_date = datetime.strptime(daily_folder_name, "%d-%m-%Y")
                if folder_date.date() < DELETE_DATE.date():
                    logging.warning(f"🧹 Deletando pasta de log real completa: {daily_path}")
                    subprocess.run(["sudo", "rm", "-rf", daily_path], check=False)
                    continue 
            except ValueError:
                pass 

            if os.path.exists(daily_path):
                for cam_folder_name in os.listdir(daily_path):
                    if not cam_folder_name.startswith('ID_'): continue
                    cam_path = os.path.join(daily_path, cam_folder_name)
                    for file_name in os.listdir(cam_path):
                        file_path = os.path.join(cam_path, file_name)
                        try:
                            if os.path.isfile(file_path) and os.path.getmtime(file_path) < DELETE_TIME_SECONDS:
                                os.remove(file_path)
                        except: pass

    # --- 2. Limpeza do LOGS_GERAIS_DIR (Histórico Completo) ---
    logging.info("--> 2/4: Limpando histórico completo em Logs_Gerais_IA.")
    if os.path.exists(LOGS_GERAIS_DIR):
        for daily_folder_name in os.listdir(LOGS_GERAIS_DIR):
            daily_path = os.path.join(LOGS_GERAIS_DIR, daily_folder_name)
            if not os.path.isdir(daily_path) or daily_folder_name == "Analise_Temporaria": continue
            try:
                folder_date = datetime.strptime(daily_folder_name, "%d-%m-%Y")
                if folder_date.date() < DELETE_DATE.date():
                    subprocess.run(["sudo", "rm", "-rf", daily_path], check=False)
            except: pass

    # --- 3. Limpeza de Imagens Críticas (Estrutura: ID_CAMERA/EVENTO_ID) ---
    logging.info("--> 3/4: Limpando imagens em Script_imagens/ID_XXX/.")
    if os.path.exists(OUTPUT_DIR):
        for cam_folder_name in os.listdir(OUTPUT_DIR):
            if not cam_folder_name.startswith('ID_'): continue
            cam_path = os.path.join(OUTPUT_DIR, cam_folder_name)
            for event_folder_name in os.listdir(cam_path):
                event_path = os.path.join(cam_path, event_folder_name)
                if os.path.isdir(event_path):
                    try:
                        if os.path.getmtime(event_path) < DELETE_TIME_SECONDS:
                            subprocess.run(["sudo", "rm", "-rf", event_path], check=False)
                    except: pass

    # --- 4. Limpeza do Cache do ZoneMinder ---
    logging.info("--> 4/4: Limpando o cache de eventos do ZoneMinder.")
    if os.path.isdir(ZM_CACHE_DIR):
        for cam_id_folder in os.listdir(ZM_CACHE_DIR):
            cam_path = os.path.join(ZM_CACHE_DIR, cam_id_folder)
            if not os.path.isdir(cam_path) or not cam_id_folder.isdigit(): continue
            for date_folder_name in os.listdir(cam_path):
                date_path = os.path.join(cam_path, date_folder_name)
                try:
                    folder_date = datetime.strptime(date_folder_name, "%Y-%m-%d")
                    if folder_date.date() < DELETE_DATE.date():
                        subprocess.run(["sudo", "rm", "-rf", date_path], check=False)
                except: continue

    logging.info("Rotina de limpeza concluída.")

if __name__ == "__main__":
    logger = logging.getLogger()
    if not any(isinstance(h, JSONErrorHandler) for h in logger.handlers):
         logger.addHandler(JSONErrorHandler())
    try:
        run_cleanup()
    except Exception:
        logging.exception("Erro fatal na execução da rotina de limpeza.")