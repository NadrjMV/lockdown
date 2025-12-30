import os
import time
import json
import logging
import shutil
from config import OUTPUT_DIR, PROCESSED_FILE
from filesystem import get_event_frames, ensure_event_folder
from deepstack import analyze_with_deepstack
from db import get_camera_groups
import stats

last_log_content = None

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

def process_event(camera_id, event_date, event_id, processed_events, event_time=None):
    global last_log_content

    # Horário Real do ZM para o log e pasta
    real_time_str = event_time.strftime("%H:%M:%S") if event_time else time.strftime("%H:%M:%S")
    real_date_str = event_time.strftime("%d-%m-%Y") if event_time else time.strftime("%d-%m-%Y")

    key = (str(camera_id), str(event_id))
    if key in processed_events: return

    frames = get_event_frames(event_id, camera_id, event_date)
    if not frames:
        processed_events.add(key)
        save_processed(processed_events)
        return

    sampled = frames[::7]
    count, objects = 0, []
    event_folder = ensure_event_folder(camera_id, event_id)
    
    if not os.path.exists(event_folder): return

    for frame in sampled:
        if not os.path.exists(event_folder): break
        detected, objs = analyze_with_deepstack(frame, camera_id, event_folder)
        if detected:
            count += 1
            objects.extend(objs)

    if count < 3:
        if os.path.exists(event_folder): 
            shutil.rmtree(event_folder, ignore_errors=True)
        processed_events.add(key)
        save_processed(processed_events)
        return

    processed_events.add(key)
    save_processed(processed_events)
    stats.increment_with_detections(event_date)

    group_ids = get_camera_groups(camera_id) or ["NENHUM"]
    daily = os.path.join(OUTPUT_DIR, real_date_str)
    camera_folder = os.path.join(daily, f"ID_{camera_id}")
    os.makedirs(camera_folder, mode=0o775, exist_ok=True)

    log_data = {
        "data_execucao":      f"{real_date_str} {real_time_str}",
        "camera":             camera_id,
        "evento":             event_id,
        "frames_analisados":  len(sampled),
        "grupo":              group_ids,
        "resultado":          f"{count} detecções em {len(sampled)} frames.",
        "objetos_detectados": objects
    }

    text = json.dumps(log_data, indent=4)
    if text == last_log_content: return

    group_str = "-".join(map(str, group_ids))
    filename = f"detections_log__ID_{camera_id}__{event_id}__{group_str}__{real_time_str.replace(':', '-')}.json"
    path = os.path.join(camera_folder, filename)

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        logging.info(f"✅ Evento {event_id} processado (Hora Real: {real_time_str})")
        last_log_content = text
    except Exception:
        logging.exception(f"Erro ao salvar log: {path}")