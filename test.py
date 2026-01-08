import os

# Caminho que o script deve monitorar
BASE_PATH = "/media/srv-sunshield/NovoVolume/Events_ZM"

def run_test():
    print(f"--- Diagnosticando acesso em: {BASE_PATH} ---")
    
    # 1. Checa existência da raiz
    if not os.path.exists(BASE_PATH):
        print(f"❌ ERRO: A pasta base não existe. Verifique se o disco está montado.")
        return

    print(f"✅ Sucesso: Pasta base encontrada.")

    try:
        # 2. Tenta listar IDs de Câmeras
        cameras = [d for d in os.listdir(BASE_PATH) if os.path.isdir(os.path.join(BASE_PATH, d))]
        if not cameras:
            print(f"⚠️ AVISO: Pasta base encontrada, mas está vazia (sem IDs de câmeras).")
            return
        
        print(f"✅ IDs de câmeras detectados: {cameras}")
        
        # 3. Tenta aprofundar na primeira câmera encontrada
        test_cam = cameras[0]
        cam_path = os.path.join(BASE_PATH, test_cam)
        dates = [d for d in os.listdir(cam_path) if os.path.isdir(os.path.join(cam_path, d))]
        
        print(f"✅ Datas encontradas na Cam {test_cam}: {dates}")
        
        if dates:
            test_date = dates[0]
            date_path = os.path.join(cam_path, test_date)
            events = os.listdir(date_path)
            print(f"✅ Eventos encontrados em {test_date}: {len(events)} pastas detectadas.")
            
            if events:
                test_evt = events[0]
                evt_path = os.path.join(date_path, test_evt)
                files = os.listdir(evt_path)
                print(f"✅ Sucesso Total: Detectados {len(files)} arquivos no evento {test_evt}.")
                
    except PermissionError:
        print(f"❌ ERRO DE PERMISSÃO: O usuário atual não consegue ler as subpastas.")
    except Exception as e:
        print(f"❌ ERRO AO LER DISCO: {e} (Pode ser erro de I/O ainda persistindo)")

if __name__ == "__main__":
    run_test()