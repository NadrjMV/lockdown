import os
import time
import logging
import shutil
from datetime import datetime, timedelta

from config import OUTPUT_DIR, ZM_CACHE_DIR, CLEANUP_RETENTION_DAYS, JSONErrorHandler 

def run_cleanup():
    """
    Função principal da limpeza. Em "OUTPUT_DIR e ZM_CACHE_DIR"
    apaga arquivos/pastas mais antigos que o limite definido.
    """

    RETENTION_DAYS = CLEANUP_RETENTION_DAYS

    # O timestamp limite (para comparação de arquivos individuais e pastas de evento)
    DELETE_TIME_SECONDS = time.time() - (RETENTION_DAYS * 86400)
    
    # Data limite (para comparar nomes de pasta de data: DD-MM-YYYY ou YYYY-MM-DD)
    DELETE_DATE = datetime.now() - timedelta(days=RETENTION_DAYS)

    logging.info(f"Iniciando rotina de limpeza. Apagando dados mais antigos do que {RETENTION_DAYS} dias ({DELETE_DATE.strftime('%d-%m-%Y %H:%M:%S')}).")

    base_dir = OUTPUT_DIR

    # --- 1. Limpeza do OUTPUT_DIR (Logs e Imagens organizados por DATA) ---
    logging.info("--> 1/3: limpando logs e imagens em OUTPUT_DIR (pastas de data).")

    if os.path.exists(base_dir):
        # Visualiza as pastas diárias (DD-MM-YYYY)
        for daily_folder_name in os.listdir(base_dir):
            daily_path = os.path.join(base_dir, daily_folder_name)
            
            # Ignora arquivos de controle e pastas que não são de data
            if not os.path.isdir(daily_path) or daily_folder_name in ('Stats', 'processed_events.txt'):
                 continue

            # Tenta deletar a pasta de data completa se ela for mais antiga que o limite
            try:
                folder_date = datetime.strptime(daily_folder_name, "%d-%m-%Y")
                if folder_date.date() < DELETE_DATE.date():
                    logging.warning(f"🧹 Deletando pasta de log diário completa: {daily_path}")
                    os.system(f"rm -rf \"{daily_path}\"")
                    continue # Se deletou a pasta, vai para a próxima
            except ValueError:
                pass # Não é uma pasta de data (ex: 'Stats'), ignora e segue

            # Se a pasta de data existe e é recente (não foi deletada), varre pastas ID_CAMERA DENTRO dela
            for cam_folder_name in os.listdir(daily_path):
                if not cam_folder_name.startswith('ID_'):
                    continue

                cam_path = os.path.join(daily_path, cam_folder_name)

                # Deleta arquivos de log JSON antigos DENTRO das pastas ID_camera
                for file_name in os.listdir(cam_path):
                    file_path = os.path.join(cam_path, file_name)
                    
                    if os.path.isfile(file_path):
                        file_mtime = os.path.getmtime(file_path)
                        if file_mtime < DELETE_TIME_SECONDS:
                            try:
                                logging.warning(f"🧹 Deletando arquivo de log JSON: {file_path}")
                                os.remove(file_path) # os.remove lida bem com espaços nativamente
                            except Exception:
                                logging.exception(f"Falha ao deletar arquivo {file_path}.")


    # --- 2. Limpeza do OUTPUT_DIR: Imagens DeepStack Legado (Estrutura: ID_CAMERA/EVENTO_ID) ---
    # Mantido para limpar estruturas antigas ou casos onde a pasta não está dentro da data
    logging.info("--> 2/3: Limpando pastas de evento (imagens DeepStack) soltas em OUTPUT_DIR.")
    
    if os.path.exists(base_dir):
        # Percorre pastas ID_CAMERA na raiz do OUTPUT_DIR
        for cam_folder_name in os.listdir(base_dir):
            # Ignora pastas de data (DD-MM-YYYY) ou arquivos soltos
            if not cam_folder_name.startswith('ID_') or not os.path.isdir(os.path.join(base_dir, cam_folder_name)):
                continue
                
            cam_path = os.path.join(base_dir, cam_folder_name)
            
            # Percorre as pastas de evento (EVENTO_ID, que contêm as imagens)
            for event_folder_name in os.listdir(cam_path):
                event_path = os.path.join(cam_path, event_folder_name)
                
                # Deletamos o diretório completo se a data de modificação for antiga
                if os.path.isdir(event_path):
                    folder_mtime = os.path.getmtime(event_path)
                    
                    if folder_mtime < DELETE_TIME_SECONDS:
                        try:
                            logging.warning(f"🧹 Deletando pasta de evento (imagens DeepStack): {event_path}")
                            os.system(f"rm -rf \"{event_path}\"") 
                        except Exception:
                            logging.exception(f"Falha ao deletar pasta de evento {event_path}.")


    # --- 3. Limpeza do Cache do ZoneMinder (ZM_CACHE_DIR/events) ---
    logging.info("--> 3/3: Limpando o cache de eventos do ZoneMinder (Imagens originais).")
    zm_events_base = os.path.join(ZM_CACHE_DIR, "events")

    if not os.path.isdir(zm_events_base):
        logging.warning(f"Pasta base de eventos do ZM não encontrada: {zm_events_base}")
        logging.info("Rotina de limpeza concluída.")
        return

    # Percorre pastas ID_CAMERA (ex: /mnt/zm_store/events/3)
    for cam_id_folder in os.listdir(zm_events_base):
        cam_path = os.path.join(zm_events_base, cam_id_folder)

        if not os.path.isdir(cam_path) or not cam_id_folder.isdigit():
            continue

        # Percorre pastas de DATA (YYYY-MM-DD)
        for date_folder_name in os.listdir(cam_path):
            date_path = os.path.join(cam_path, date_folder_name)
            
            # Valida o formato YYYY-MM-DD (usado pelo ZM)
            try:
                folder_date = datetime.strptime(date_folder_name, "%Y-%m-%d")
            except ValueError:
                continue

            if folder_date.date() < DELETE_DATE.date():
                try: 
                    # Apaga a pasta inteira da data (com todos os eventos daquele dia)
                    logging.warning(f"🧹 ZM Cache: Deletando pasta de data antiga {date_folder_name} (Câmera {cam_id_folder}).")
                    os.system(f"sudo rm -rf \"{date_path}\"") 
                except Exception:
                    logging.exception(f"ZM Cache: Falha ao deletar pasta {date_path}.")

    logging.info("Rotina de limpeza concluída.")

if __name__ == "__main__":
    # Garante que o handler de erro JSON esteja ativo
    logger = logging.getLogger()
    if not any(isinstance(h, JSONErrorHandler) for h in logger.handlers):
         logger.addHandler(JSONErrorHandler())
        
    try:
        run_cleanup()
    except Exception:
        logging.exception("Erro fatal na execução da rotina de limpeza.")