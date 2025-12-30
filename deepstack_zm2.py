import mysql.connector
import requests
from PIL import Image
import urllib3
import os
import time
import re
import shutil  # Para remover pastas se nao houver deteccao
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import json
import datetime
import threading

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuracao do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S"
)

# --- NOVA: Handler personalizado para gerar logs de erro em JSON ---
class JSONErrorHandler(logging.Handler):
    def emit(self, record):
        try:
            if record.levelno >= logging.ERROR:
                current_date = time.strftime("%d-%m-%Y")
                current_time = time.strftime("%H:%M:%S")
                daily_folder = os.path.join(output_dir, current_date)
                if not os.path.exists(daily_folder):
                    os.makedirs(daily_folder)
                error_data = {
                    "data_execucao": f"{current_date} {current_time}",
                    "nivel": record.levelname,
                    "mensagem": record.getMessage(),
                    "traceback": record.exc_text if record.exc_info else ""
                }
                error_log_filename = f"error_log_{current_time}.json"
                error_log_path = os.path.join(daily_folder, error_log_filename)
                with open(error_log_path, "w", encoding="utf-8") as f:
                    json.dump(error_data, f, indent=4)
                logging.info(f"Log de erro gerado em: {error_log_path}")
        except Exception:
            self.handleError(record)

# Adiciona o handler de erros JSON ao logger
logger = logging.getLogger()
logger.addHandler(JSONErrorHandler())

# ============================
# CONFIGURACOES
# ============================
prefix = "camera"
zmuser = "admin"
zmpass = "sunshield1414"
zmaddr = "192.168.1.39"
deepstackaddr = "localhost:5001"  # Ou o IP do seu servidor DeepStack

# NOVO: Caminho alterado para /var/www/html/Script_imagens
output_dir = "/var/www/html/Script_imagens"
# Observa /var/cache/zoneminder/events/<camera_id>/<YYYY-MM-DD>/<event_id>
zm_cache_dir = "/var/cache/zoneminder"

# Lista de IDs das cameras
zmmoids = [11, 12, 13, 14, 24, 25, 26, 27, 45, 28, 29, 30, 31, 32, 50, 33, 34, 38, 39]
# Arquivo que guarda eventos ja processados
processed_events_file = os.path.join(output_dir, "processed_events.txt")
processed_events = set()  # (camera_id, event_id) ja processados

# Carrega o arquivo de eventos processados, se existir
if os.path.exists(processed_events_file):
    try:
        with open(processed_events_file, "r") as f:
            for line in f:
                line = line.strip()
                parts = line.split("|")
                if len(parts) == 2:
                    cam_id_str, evt_id_str = parts
                    processed_events.add((cam_id_str, evt_id_str))
    except Exception as e:
        logging.exception("Erro ao carregar o arquivo de eventos processados.")

# Variavel global para armazenar o conteudo do ultimo log gerado
last_log_content = None

# ============================
# FUNCOES AUXILIARES
# ============================
def ensure_camera_folder(camera_id):
    folder = os.path.join(output_dir, f"ID_{camera_id}")
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
            logging.info(f"Pasta criada para camera {camera_id}: {folder}")
        except Exception as e:
            logging.exception(f"Erro ao criar pasta para camera {camera_id}: {folder}")
            raise
    return folder

def ensure_event_folder(camera_id, event_id):
    try:
        camera_folder = ensure_camera_folder(camera_id)
        event_folder = os.path.join(camera_folder, str(event_id))
        if not os.path.exists(event_folder):
            os.makedirs(event_folder)
            logging.info(f"Pasta de evento criada para camera {camera_id}, evento {event_id}: {event_folder}")
        return event_folder
    except Exception as e:
        logging.exception(f"Erro ao criar pasta de evento para camera {camera_id}, evento {event_id}")
        raise

# Pre-cria as pastas para todas as cameras
for cam_id in zmmoids:
    ensure_camera_folder(cam_id)

# --- TRATAMENTO ROBUSTO PARA CONEXAO COM O BANCO DE DADOS ---
def get_db_connection(retries=3, delay=2):
    attempt = 0
    while attempt < retries:
        try:
            connection = mysql.connector.connect(
                host="localhost",
                user="zmuser",            # NAO ALTERE ESSE VALOR
                password="sunshield1414", # MUITO MENOS ESSE
                database="zm"             # Nome do banco de dados do ZoneMinder
            )
            return connection
        except mysql.connector.Error as e:
            attempt += 1
            logging.error(f"Tentativa {attempt} de {retries} - Erro ao conectar ao banco de dados: {e}")
            time.sleep(delay)
    raise Exception("Nao foi possivel conectar ao banco de dados apos varias tentativas.")

def get_latest_event(zmmoid):
    """(Opcional) Pode ser usado para validacao se desejar."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT Id, StartDateTime 
            FROM Events 
            WHERE MonitorId = %s 
            ORDER BY StartDateTime DESC 
            LIMIT 1;
        """, (zmmoid,))
        event = cursor.fetchone()
        cursor.close()
        conn.close()
        if event:
            return event['Id'], event['StartDateTime']
    except Exception as e:
        logging.exception(f"Erro ao obter o ultimo evento para a camera {zmmoid}")
    return None, None

def get_event_frames(event_id, camera_id, event_date):
    """
    Retorna a lista de todos os frames encontrados na pasta do evento,
    ordenados em ordem crescente.
    """
    try:
        event_path = os.path.join(zm_cache_dir, "events", str(camera_id), event_date, str(event_id))
        if not os.path.exists(event_path):
            logging.error(f"Pasta do evento nao encontrada: {event_path}")
            return []
        frames = []
        try:
            frame_files = sorted([
                f for f in os.listdir(event_path)
                if f.endswith('-capture.jpg') and f.split('-')[0].isdigit()
            ])
        except Exception as e:
            logging.exception(f"Erro ao listar arquivos em {event_path}")
            return []
        for file_name in frame_files:
            frames.append(os.path.join(event_path, file_name))
        return frames
    except Exception as e:
        logging.exception(f"Erro na funcao get_event_frames para o evento {event_id} da camera {camera_id}")
        return []

ALLOWED_LABELS = {"person", "car"}

# --- TRATAMENTO ROBUSTO E RETENTATIVAS PARA A CONEXAO COM O DEEPSTACK ---
def analyze_with_deepstack(image_path, zmmoid, event_folder, retries=3, delay=2):
    try:
        with open(image_path, "rb") as img_file:
            image_data = img_file.read()
    except Exception as e:
        logging.exception(f"Erro ao ler a imagem {image_path} da camera {zmmoid}")
        return False, []
    attempt = 0
    detected_objects = []
    while attempt < retries:
        try:
            response = requests.post(
                f"http://{deepstackaddr}/v1/vision/detection",
                files={"image": image_data},
                data={"min_confidence": 0.65}
            ).json()
            break
        except requests.RequestException as e:
            attempt += 1
            logging.error(f"Tentativa {attempt} de {retries} - Erro ao conectar ao DeepStack para camera {zmmoid}: {e}")
            time.sleep(delay)
    else:
        return False, detected_objects

    if "predictions" not in response:
        logging.info(f"Nenhuma deteccao para a imagem {image_path} da camera {zmmoid}")
        return False, detected_objects
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as e:
        logging.exception(f"Erro ao abrir a imagem {image_path} da camera {zmmoid}")
        return False, detected_objects
    detected = False
    for i, obj in enumerate(response["predictions"]):
        try:
            label = obj["label"].lower().replace(" ", "_")
            if label not in ALLOWED_LABELS:
                continue
            confidence = obj.get("confidence", 0) * 100
            x_min, y_min, x_max, y_max = map(int, [obj["x_min"], obj["y_min"], obj["x_max"], obj["y_max"]])
            cropped = image.crop((x_min, y_min, x_max, y_max))
            cropped_filename = f"{prefix}_{zmmoid}_{int(time.time()*1000)}_{i}_{label}.jpg"
            cropped_path = os.path.join(event_folder, cropped_filename)
            cropped.save(cropped_path)
            logging.info(f"🔍 Objeto '{label}' salvo: {cropped_path} (Confianca: {confidence:.2f}%)")
            detected_objects.append(f"{label} (Confianca: {confidence:.2f}%)")
            detected = True
        except Exception as e:
            logging.exception(f"Erro ao processar deteccao no frame {image_path} para a camera {zmmoid}")
    return detected, detected_objects

def process_event(camera_id, event_date, event_id):
    global last_log_content
    try:
        if (str(camera_id), str(event_id)) in processed_events:
            logging.info(f"Evento {event_id} da camera {camera_id} ja foi processado. Pulando...")
            return

        logging.info(f"Novo evento detectado: Camera {camera_id}, Data {event_date}, Evento {event_id}")
        event_folder = ensure_event_folder(camera_id, event_id)
        frames = get_event_frames(event_id, camera_id, event_date)

        if not frames:
            logging.info(f"❌ Nenhum frame encontrado para o evento {event_id} da camera {camera_id}.")
            processed_events.add((str(camera_id), str(event_id)))
            with open(processed_events_file, "w") as pf:
                for (cam_id_str, evt_id_str) in processed_events:
                    pf.write(f"{cam_id_str}|{evt_id_str}\n")
            return

        # --- NOVA LÓGICA: amostragem de 1 em 5 frames e contagem de detecções ---
        sampled_frames = frames[::5]
        detection_count = 0
        detected_objects = []

        for frame in sampled_frames:
            logging.info(f"Enviando frame {frame} da camera {camera_id} para o DeepStack...")
            detected, objects = analyze_with_deepstack(frame, camera_id, event_folder)
            if detected:
                detection_count += 1
                detected_objects.extend(objects)
                logging.info(f"✅ Deteccao de objetos realizada com sucesso para o frame {frame} da camera {camera_id}.")
            else:
                logging.info(f"⚠️ Nenhum objeto detectado para o frame {frame} da camera {camera_id}.")

        # Se menos de 5 frames amostrados tiveram detecção, descarta o evento
        if detection_count < 5:
            logging.info(f"❌ Apenas {detection_count} detecções em {len(sampled_frames)} frames ({camera_id}, evento {event_id}). Evento descartado.")
            try:
                shutil.rmtree(event_folder, ignore_errors=True)
                logging.info(f"Pasta do evento removida: {event_folder}")
            except Exception as e:
                logging.exception(f"Erro ao remover a pasta {event_folder}")
            processed_events.add((str(camera_id), str(event_id)))
            with open(processed_events_file, "w") as pf:
                for (cam_id_str, evt_id_str) in processed_events:
                    pf.write(f"{cam_id_str}|{evt_id_str}\n")
            return

        # Evento considerado OK — registra como processado e gera log
        processed_events.add((str(camera_id), str(event_id)))
        with open(processed_events_file, "w") as pf:
            for (cam_id_str, evt_id_str) in processed_events:
                pf.write(f"{cam_id_str}|{evt_id_str}\n")

        current_date = time.strftime("%d-%m-%Y")
        current_time = time.strftime("%H:%M:%S")
        daily_folder = os.path.join(output_dir, current_date)
        if not os.path.exists(daily_folder):
            os.makedirs(daily_folder)

        log_filename = f"detections_log_ID{camera_id}_{current_time}.json"
        log_path = os.path.join(daily_folder, log_filename)

        log_data = {
            "data_execucao": f"{current_date} {current_time}",
            "camera": camera_id,
            "evento": event_id,
            "frames_analisados": len(sampled_frames),
            "resultado": f"HOUVE {detection_count} DETECCOES EM {len(sampled_frames)} FRAMES AMOSTRADOS.",
            "objetos_detectados": detected_objects
        }

        log_text = json.dumps(log_data, indent=4)

        if log_text == last_log_content:
            logging.info("O log gerado e igual ao anterior. Nao criando novo arquivo de log.")
            return
        else:
            last_log_content = log_text

        with open(log_path, "w") as f:
            f.write(log_text)

        logging.info(f"Log do evento gerado em: {log_path}")
    except Exception as e:
        logging.exception(f"Erro no processamento do evento {event_id} da camera {camera_id}")

class NewEventHandler(FileSystemEventHandler):
    def __init__(self, observer):
        super().__init__()
        self.observer = observer
        self.watched_dates = set()

    def on_created(self, event):
        # só diretórios nos interessam
        if not event.is_directory:
            return

        parts = event.src_path.strip(os.sep).split(os.sep)[-3:]
        # /…/events/<camera_id>/<YYYY-MM-DD>
        if len(parts) == 2 and parts[0].isdigit() and re.match(r"\d{4}-\d{2}-\d{2}", parts[1]):
            date_path = event.src_path
            if date_path not in self.watched_dates:
                self.observer.schedule(self, date_path, recursive=False)
                self.watched_dates.add(date_path)
                logging.info(f"➕ Watch agendado em: {date_path}")
            return

        # /…/events/<camera_id>/<YYYY-MM-DD>/<event_id>
        parts = event.src_path.strip(os.sep).split(os.sep)[-3:]
        if len(parts) == 3:
            camera_id, date_str, event_id = parts
            if camera_id.isdigit() and re.match(r"\d{4}-\d{2}-\d{2}", date_str) and event_id.isdigit():
                cam = int(camera_id)
                if cam in zmmoids:
                    time.sleep(5)
                    process_event(cam, date_str, int(event_id))
                else:
                    logging.info(f"Ignorando câmera não configurada: {camera_id}")

def start_daemon_watch():
    base = os.path.join(zm_cache_dir, "events")
    observer = Observer()
    handler  = NewEventHandler(observer)

    # 1) Vigia só a raiz para capturar novas pastas de câmera
    observer.schedule(handler, base, recursive=False)

    # 2) Para cada câmera, agenda watcher não-recursivo em /events/<camera_id>
    for cam_id in zmmoids:
        cam_path = os.path.join(base, str(cam_id))
        if os.path.isdir(cam_path):
            observer.schedule(handler, cam_path, recursive=False)

            # 3) Para cada data já existente, agenda não-recursivo
            for date_dir in os.listdir(cam_path):
                date_path = os.path.join(cam_path, date_dir)
                if os.path.isdir(date_path) and date_path not in handler.watched_dates:
                    observer.schedule(handler, date_path, recursive=False)
                    handler.watched_dates.add(date_path)

    observer.start()
    logging.info(f"Iniciando monitoramento otimizado em: {base}")

    # Loop com contador para logar a cada 15 segundos
    counter = 0
    try:
        while True:
            time.sleep(1)
            counter += 1
            if counter >= 15:
                logging.info("🚨 Aguardando novos eventos... 🚨")
                counter = 0
    except KeyboardInterrupt:
        logging.info("Encerrando daemon (CTRL+C detectado).")
        observer.stop()
    observer.join()

if __name__ == "__main__":
    try:
        start_daemon_watch()
    except Exception as e:
        logging.exception("Erro no daemon principal.")