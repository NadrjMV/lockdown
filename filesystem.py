import os
import logging
from config import OUTPUT_DIR, ZM_CACHE_DIR

def ensure_camera_folder(camera_id):
    path = os.path.join(OUTPUT_DIR, f"ID_{camera_id}")
    os.makedirs(path, mode=0o775, exist_ok=True)
    return path

def ensure_event_folder(camera_id, event_id):
    cam_folder = ensure_camera_folder(camera_id)
    event_folder = os.path.join(cam_folder, str(event_id))
    os.makedirs(event_folder, mode=0o775, exist_ok=True)
    return event_folder

def get_event_frames(event_id, camera_id, event_date):
    # Agora monta o caminho usando o novo volume sem a subpasta redundante 'events'
    base = os.path.join(
        ZM_CACHE_DIR,
        str(camera_id),
        event_date,
        str(event_id)
    )

    if not os.path.isdir(base):
        logging.error(f"Pasta de frames ZM não encontrada: {base}")
        return []

    files = sorted(
        f for f in os.listdir(base)
        if f.endswith("-capture.jpg") and f.split("-")[0].isdigit()
    )

    return [os.path.join(base, f) for f in files]