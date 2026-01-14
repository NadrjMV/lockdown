import os
import time
import json
import logging
import shutil
from config import OUTPUT_DIR, LOGS_GERAIS_DIR, PROCESSED_FILE, IA_ALERTS_FILE
from filesystem import get_event_frames
from deepstack import analyze_with_deepstack
from db import get_camera_groups
import stats

last_log_content = None
alert_cooldowns = {}
COOLDOWN_SECONDS = 300 

def load_processed():
    s = set()
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE) as f:
            for line in f:
                try:
                    cam, evt = line.strip().split("|")
                    s.add((cam, evt))
                except: continue
    return s

def save_processed(processed):
    with open(PROCESSED_FILE, "w") as f:
        for cam, evt in processed:
            f.write(f"{cam}|{evt}\n")

def update_alert_stream(new_alert):
    alerts = []
    if os.path.exists(IA_ALERTS_FILE):
        try:
            with open(IA_ALERTS_FILE, 'r', encoding='utf-8') as f:
                alerts = json.load(f)
        except: alerts = []
    alerts.insert(0, new_alert)
    alerts = alerts[:20]
    with open(IA_ALERTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(alerts, f, indent=4)

def process_event(camera_id, event_date, event_id, processed_events):
    global alert_cooldowns
    key = (str(camera_id), str(event_id))
    if key in processed_events: return

    frames = get_event_frames(event_id, camera_id, event_date)
    if not frames:
        processed_events.add(key)
        save_processed(processed_events)
        return

    sampled = frames[::7]
    count = 0
    objects = []
    
    work_dir = os.path.join(LOGS_GERAIS_DIR, "Analise_Temporaria", f"{camera_id}_{event_id}")
    os.makedirs(work_dir, exist_ok=True)

    for frame in sampled:
        detected, objs = analyze_with_deepstack(frame, camera_id, work_dir)
        if detected:
            count += 1
            objects.extend(objs)

    if count < 3:
        shutil.rmtree(work_dir, ignore_errors=True)
        processed_events.add(key)
        save_processed(processed_events)
        return

    current_time = time.time()
    primary_label = objects[0].split(' ')[0] if objects else "person"
    alert_key = f"{camera_id}_{primary_label}"
    is_critical = (current_time - alert_cooldowns.get(alert_key, 0)) > COOLDOWN_SECONDS
    
    if is_critical:
        alert_cooldowns[alert_key] = current_time

    processed_events.add(key)
    save_processed(processed_events)
    stats.increment_with_detections(event_date)

    date_str = time.strftime("%d-%m-%Y")
    time_str = time.strftime("%H:%M:%S")
    groups = get_camera_groups(camera_id)
    main_group = groups[0] if groups else 10

    log_data = {
        "data_execucao": f"{date_str} {time_str}",
        "camera": camera_id,
        "evento": event_id,
        "is_critical": is_critical,
        "grupo": groups,
        "resultado": f"{count} detecções.",
        "objetos_detectados": list(set(objects))
    }

    # 1. HISTÓRICO COMPLETO (Logs_Gerais_IA)
    geral_path = os.path.join(LOGS_GERAIS_DIR, date_str, f"ID_{camera_id}")
    os.makedirs(geral_path, exist_ok=True)
    with open(os.path.join(geral_path, f"log_{event_id}.json"), "w") as f:
        json.dump(log_data, f, indent=4)

    if is_critical:
        # 2. LOG DE EVENTO REAL (Nomenclatura idêntica à imagem)
        real_log_folder = os.path.join(OUTPUT_DIR, date_str, f"ID_{camera_id}")
        os.makedirs(real_log_folder, exist_ok=True)
        
        # Padrão da imagem: detections_log__ID_156__252266__11__11:22:27.json
        file_name = f"detections_log__ID_{camera_id}__{event_id}__{main_group}__{time_str}.json"
        real_log_path = os.path.join(real_log_folder, file_name)
        
        with open(real_log_path, "w") as f:
            json.dump(log_data, f, indent=4)

        # 3. IMAGENS DO EVENTO (Pasta Fixa)
        lockdown_path = os.path.join(OUTPUT_DIR, f"ID_{camera_id}", str(event_id))
        os.makedirs(os.path.dirname(lockdown_path), exist_ok=True)
        
        if os.path.exists(lockdown_path): shutil.rmtree(lockdown_path)
        shutil.move(work_dir, lockdown_path)
        
        # Comentei pra parar de gerar o arquivo alert_{id}.log
        # with open(os.path.join(lockdown_path, f"alert_{event_id}.json"), "w") as f:
        #     json.dump(log_data, f, indent=4)
            
        update_alert_stream(log_data)
        logging.info(f"🚨 ALERTA REAL: {file_name}")
    else:
        shutil.rmtree(work_dir, ignore_errors=True)
        logging.info(f"🔇 Log silencioso arquivado.")