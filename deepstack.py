import requests
import time
import os
import shutil
import logging
import subprocess
from PIL import Image
from config import DEEPSTACK_ADDR, PREFIX

ALLOWED_LABELS = {"person", "car"}

def analyze_with_deepstack(image_path, zmmoid, event_folder, retries=3, delay=2):
    try:
        with open(image_path, "rb") as img_file:
            image_data = img_file.read()
    except Exception as e:
        logging.exception(f"Erro ao ler a imagem {image_path} da câmera {zmmoid}")
        return False, []

    attempt = 0
    while attempt < retries:
        try:
            response = requests.post(
                f"http://{DEEPSTACK_ADDR}/v1/vision/detection",
                files={"image": image_data},
                data={"min_confidence": 0.65}
            ).json()
            break
        except requests.RequestException as e:
            attempt += 1
            logging.error(f"Tentativa {attempt}/{retries} falhou no DeepStack: {e}")
            time.sleep(delay)
    else:
        return False, []

    if "predictions" not in response:
        logging.info(f"Nenhuma detecção para a imagem {image_path}")
        return False, []

    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as e:
        logging.exception(f"Erro ao abrir {image_path}")
        return False, []

    detected = False
    detected_objects = []
    ts = int(time.time() * 1000)
    full_saved = False

    for i, obj in enumerate(response["predictions"]):
        label = obj["label"].lower().replace(" ", "_")
        if label not in ALLOWED_LABELS:
            continue

        # Salva o frame inteiro apenas na primeira detecção
        if not full_saved:
            full_filename = f"{PREFIX}_{zmmoid}_{ts}_frame.jpg"
            full_path = os.path.join(event_folder, full_filename)
            
            # Nome fixo pra facilitar o carregamento no dashboard
            preview_path = os.path.join(event_folder, "preview.jpg")
            
            try:
                shutil.copy(image_path, full_path)
                # Cria a cópia com nome fixo pro preview
                shutil.copy(image_path, preview_path)
                
                # --- CORREÇÃO DE PERMISSÃO (Subprocess) ---
                subprocess.run(["sudo", "chown", "www-data:www-data", full_path], check=False)
                subprocess.run(["sudo", "chown", "www-data:www-data", preview_path], check=False)
                
                logging.info(f"📸 Frame inteiro e preview salvos em: {event_folder}")
            except Exception:
                logging.exception(f"Erro ao salvar o frame inteiro ou preview em {event_folder}")
            full_saved = True

        confidence = obj.get("confidence", 0) * 100
        x_min, y_min, x_max, y_max = map(int, (
            obj["x_min"], obj["y_min"], obj["x_max"], obj["y_max"]
        ))
        cropped = image.crop((x_min, y_min, x_max, y_max))
        cropped_filename = f"{PREFIX}_{zmmoid}_{ts}_{i}_{label}.jpg"
        cropped_path = os.path.join(event_folder, cropped_filename)
        try:
            cropped.save(cropped_path)
            
            # --- CORREÇÃO DE PERMISSÃO (Subprocess) ---
            subprocess.run(["sudo", "chown", "www-data:www-data", cropped_path], check=False)
            
            logging.info(f"🔍 Recorte '{label}' salvo: {cropped_path} ({confidence:.2f}%)")
        except Exception:
            logging.exception(f"Erro ao salvar recorte {cropped_path}")

        detected_objects.append(f"{label} ({confidence:.2f}%)")
        detected = True

    return detected, detected_objects