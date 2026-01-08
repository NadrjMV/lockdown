import os
import time
import logging
import json
import urllib3
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)

PREFIX          = "camera"
ZMUSER          = "zmuser"
ZMPASS          = "sunshield1414"
ZM_ADDR         = "192.168.1.39"
DEEPSTACK_ADDR  = "localhost:5001"

# Estrutura de Pastas
OUTPUT_DIR      = "/media/srv-sunshield/NovoVolume/Script_imagens"
LOGS_GERAIS_DIR = "/media/srv-sunshield/NovoVolume/Logs_Gerais_IA"
ZM_CACHE_DIR    = "/media/srv-sunshield/NovoVolume/Events_ZM"
ZM_LOGS_DIR     = "/media/srv-sunshield/NovoVolume/Logs_ZM"

PROCESSED_FILE  = os.path.join(OUTPUT_DIR, "processed_events.txt")
IA_MONITORING_FILE = "/var/www/html/ia_monitoring_cameras.json"
IA_ALERTS_FILE = "/var/www/html/ia_alerts.json"

CLEANUP_RETENTION_DAYS   = 6
CLEANUP_INTERVAL_MINUTES = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.join(ZM_LOGS_DIR, "sentinel_ia.log")),
        logging.StreamHandler()
    ]
)

class JSONErrorHandler(logging.Handler):
    def emit(self, record):
        if record.levelno < logging.ERROR: return
        date_str = time.strftime("%d-%m-%Y")
        time_str = time.strftime("%H:%M:%S")
        daily_folder = os.path.join(LOGS_GERAIS_DIR, date_str, "ERROS")
        os.makedirs(daily_folder, exist_ok=True)
        error_data = {
            "data_execucao": f"{date_str} {time_str}",
            "nivel": record.levelname,
            "mensagem": record.getMessage()
        }
        path = os.path.join(daily_folder, f"error_{time_str.replace(':','-')}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(error_data, f, indent=4)
        except: pass