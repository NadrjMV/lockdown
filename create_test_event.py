import os
import json
import time
import logging
from config import OUTPUT_DIR 

# --- DADOS FICTÍCIOS PRA TESTE ---
# Mude eesse te número pra quantidade de arquivos que vai criar
NUMBER_OF_EVENTS_TO_CREATE = 2

# ID inicial do evento pra começar a contagem
BASE_EVENT_ID = 90000          

# TEST_GROUPS -> as cameras sao vinculas a apenas um grupo
TEST_CAMERA_ID = 3
TEST_GROUPS    = [5]
TEST_DETECTIONS = [
    "person (Confianca: 92.50%)",
    "person (Confianca: 85.10%)",
    "car (Confianca: 78.00%)"
]
# -----------------------------------

def create_mock_event(event_id):
    """
    Cria um arquivo de log JSON pra um ID de evento específico.
    """
    date_str = time.strftime("%d-%m-%Y")
    time_str = time.strftime("%H:%M:%S")

    # 1. Monta o conteúdo do JSON
    log_data = {
        "data_execucao":      f"{date_str} {time_str}",
        "camera":             TEST_CAMERA_ID,
        "evento":             event_id,
        "frames_analisados":  10,
        "grupo":              TEST_GROUPS,
        "resultado":          f"{len(TEST_DETECTIONS)} detecções em 10 frames.",
        "objetos_detectados": TEST_DETECTIONS
    }
    
    # 2. Monta o nome do arquivo e o path
    group_str = "-".join(map(str, TEST_GROUPS))
    part_id = f"ID_{TEST_CAMERA_ID}"
    
    # O nome do arquivo usa a hora (HH:MM:SS) pra garantir unicidade, pois a ID do evento está no corpo
    filename = f"detections_log__{part_id}__{event_id}__{group_str}__{time_str}.json"
    
    # O path completo: OUTPUT_DIR/DD-MM-YYYY/ID_CAMERA/filename
    daily_folder = os.path.join(OUTPUT_DIR, date_str)
    camera_folder = os.path.join(daily_folder, part_id)
    file_path = os.path.join(camera_folder, filename)

    # 3. Garante que as pastas existam e com permissões corretas
    os.makedirs(camera_folder, exist_ok=True)
    os.chmod(daily_folder, 0o775)
    os.chmod(camera_folder, 0o775)

    # 4. Grava o arquivo JSON
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=4)
        
        print(f"✅ Evento de teste criado: ID {event_id} (Arquivo: {filename})")
        
    except Exception as e:
        print(f"❌ Falha ao gravar o arquivo de teste (ID {event_id}): {e}")

def run_test_creation():
    """
    Função principal que gerencia o loop de criação de eventos.
    """
    print(f"--- Gerando {NUMBER_OF_EVENTS_TO_CREATE} eventos de teste ---")
    
    for i in range(NUMBER_OF_EVENTS_TO_CREATE):
        # Gera um ID de evento único (e sequencial)
        event_id = BASE_EVENT_ID + i 
        
        # Cria o evento
        create_mock_event(event_id)
        
        # Espera 1 segundo. ESSENCIAL pra garantir que o timestamp no nome do arquivo seja único.
        time.sleep(1) 
    
    print("--- Geração de eventos concluída ---")


if __name__ == "__main__":
    run_test_creation()
