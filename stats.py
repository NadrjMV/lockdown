import os
import json
import time
import logging
from config import OUTPUT_DIR

def _ensure_stats_dir(date_str):
    year, month, day = date_str.split('-')
    month_num = str(int(month))
    path = os.path.join(OUTPUT_DIR, 'Stats', year, month_num, day)
    os.makedirs(path, exist_ok=True)
    return path

def _load_stats(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            logging.exception(f"Erro ao ler estatísticas em {file_path}")
    return {'total': 0, 'with_detections': 0, 'last_updated': None}

def _save_stats(file_path, data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception:
        logging.exception(f"Erro ao gravar estatísticas em {file_path}")

def increment_total(date_str):
    """Incrementa total de eventos gerados no dia."""
    stats_dir = _ensure_stats_dir(date_str)
    file_path = os.path.join(stats_dir, 'events_stats.json')
    data = _load_stats(file_path)
    data['total'] = data.get('total', 0) + 1
    data['last_updated'] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_stats(file_path, data)

def increment_with_detections(date_str):
    """Incrementa contagem de eventos que tiveram ao menos uma detecção."""
    stats_dir = _ensure_stats_dir(date_str)
    file_path = os.path.join(stats_dir, 'events_stats.json')
    data = _load_stats(file_path)
    data['with_detections'] = data.get('with_detections', 0) + 1
    data['last_updated'] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_stats(file_path, data)

def generate_monthly_summary(year: str, month: str):
    """(inalterado)"""
    month_num = str(int(month))
    month_dir = os.path.join(OUTPUT_DIR, 'Stats', year, month_num)
    if not os.path.isdir(month_dir):
        logging.warning(f"Stats: pasta do mês não existe: {month_dir}")
        return

    total = 0
    with_det = 0
    for day in os.listdir(month_dir):
        stat_file = os.path.join(month_dir, day, 'events_stats.json')
        if os.path.isfile(stat_file):
            data = _load_stats(stat_file)
            total  += data.get('total', 0)
            with_det += data.get('with_detections', 0)

    summary = {
        'year': year,
        'month': month_num,
        'total_events': total,
        'with_detections': with_det,
        'generated_at': time.strftime("%Y-%m-%d %H:%M:%S")
    }
    out_path = os.path.join(month_dir, f"{year}_{month_num}_summary.json")
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=4)
        logging.info(f"Resumo mensal gerado em: {out_path}")
    except Exception:
        logging.exception(f"Falha ao gravar resumo mensal em: {out_path}")

