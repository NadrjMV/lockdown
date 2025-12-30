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

OUTPUT_DIR      = "/media/srv-sunshield/NovoVolume/Script_imagens"
ZM_CACHE_DIR    = "/media/srv-sunshield/NovoVolume/Events_ZM" # Onde estao os eventos
ZM_LOGS_DIR     = "/media/srv-sunshield/NovoVolume/Logs_ZM"   # Onde estao os logs do ZM
PROCESSED_FILE  = os.path.join(OUTPUT_DIR, "processed_events.txt")

# Arquivo para o dashboard de monitoramento no lockdown
IA_MONITORING_FILE = "/var/www/html/ia_monitoring_cameras.json"

CLEANUP_RETENTION_DAYS   = 1
CLEANUP_INTERVAL_MINUTES = 60

# Configura o log pra salvar no arquivo dentro do novo volume e mostrar no console
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
        if record.levelno < logging.ERROR:
            return

        date_str = time.strftime("%d-%m-%Y")
        time_str = time.strftime("%H:%M:%S")

        daily_folder = os.path.join(OUTPUT_DIR, date_str)
        os.makedirs(daily_folder, exist_ok=True)

        cam = getattr(record, "camera_id", "general")

        error_data = {
            "data_execucao": f"{date_str} {time_str}",
            "nivel": record.levelname,
            "mensagem": record.getMessage(),
            "traceback": record.exc_text or ""
        }

        path = os.path.join(daily_folder, f"error_log_ID_{cam}_{time_str}.json")

        with open(path, "w", encoding="utf-8") as f:
            json.dump(error_data, f, indent=4)

logger = logging.getLogger()
logger.addHandler(JSONErrorHandler())