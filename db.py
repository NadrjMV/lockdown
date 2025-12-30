import mysql.connector
import time
import logging
from config import ZMUSER, ZMPASS

def get_db_connection(retries=3, delay=2):
    attempt = 0
    while attempt < retries:
        try:
            return mysql.connector.connect(
                host="localhost",
                user=ZMUSER,
                password=ZMPASS,
                database="zm"
            )
        except mysql.connector.Error as e:
            attempt += 1
            logging.error(f"Tentativa {attempt}/{retries} falhou: {e}")
            time.sleep(delay)
    raise Exception("Não conectou ao MySQL após várias tentativas.")

def get_latest_event(zmmoid):
    """Retorna (Id, StartDateTime) do último evento."""
    conn = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT Id, StartDateTime
            FROM Events
            WHERE MonitorId = %s
            ORDER BY StartDateTime DESC
            LIMIT 1
        """, (zmmoid,))
        row = cursor.fetchone()
        cursor.close()
        return (row['Id'], row['StartDateTime']) if row else (None, None)
    except Exception:
        logging.exception(f"get_latest_event: falha ao buscar evento para monitor {zmmoid}")
        return (None, None)
    finally:
        if conn:
            conn.close()

def get_camera_groups(camera_id):
    """
    Retorna uma lista de IDs (inteiros) de todos os grupos aos quais
    a câmera 'camera_id' pertence. Se falhar, retorna lista vazia.
    """
    conn = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.Id
              FROM Groups AS g
              JOIN Groups_Monitors AS gm ON gm.groupId = g.Id
             WHERE gm.monitorId = %s
        """, (camera_id,))
        # extrai apenas o primeiro campo de cada linha (o próprio Id)
        groups = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return groups
    except Exception:
        logging.exception(f"get_camera_groups: não foi possível buscar grupos para câmera {camera_id}")
        return []
    finally:
        if conn:
            conn.close()

def get_active_monitor_ids():
    """
    Retorna apenas os IDs das câmeras que estão ATIVAS no ZM.
    Filtra câmeras deletadas ou desativadas (Function != 'None').
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Só filtra quem tem função definida (Monitor, Modect, etc)
        cursor.execute("""
            SELECT Id
            FROM Monitors
            WHERE Function != 'None'
            ORDER BY Id ASC
        """)
        
        monitors = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        logging.info(f"Câmeras ativas carregadas do DB: {monitors}")
        return monitors
    
    except Exception:
        logging.exception("get_active_monitor_ids: falha ao buscar monitores ativos do DB.")
        return []
    finally:
        if conn:
            pass