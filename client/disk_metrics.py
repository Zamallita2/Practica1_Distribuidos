import os
import sys
import time
import platform
import random
import psutil
import subprocess

def detect_disk_type(device, mountpoint):
    """
    Detecta el tipo real de disco (SSD/HDD).
    Compatible con Windows y Linux.
    """

    system = platform.system()

    # Windows
    if system == "Windows":
        try:
            drive = os.path.splitdrive(mountpoint)[0].replace(":", "")

            command = [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Partition -DriveLetter '{drive}' | "
                "Get-Disk | Get-PhysicalDisk).MediaType"
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5
            )

            media_type = result.stdout.strip().upper()

            if "SSD" in media_type:
                return "SSD"

            if "HDD" in media_type:
                return "HDD"

        except Exception:
            pass

    # Linux
    elif system == "Linux":
        try:
            result = subprocess.run(
                ["lsblk", "-ndo", "ROTA", device],
                capture_output=True,
                text=True,
                timeout=5
            )

            rota = result.stdout.strip()

            if rota == "0":
                return "SSD"

            if rota == "1":
                return "HDD"

        except Exception:
            pass

    return "Desconocido"

def get_first_disk_metrics():
    """
    Detecta automáticamente el primer disco del sistema y extrae sus métricas.
    Compatible con Linux y Windows.
    """
    partitions = psutil.disk_partitions(all=False)
    if not partitions:
        return None
    
    # Tomar la primera partición/disco detectado
    first_part = partitions[0]
    mountpoint = first_part.mountpoint
    device = first_part.device
    
    # Obtener uso de espacio
    try:
        usage = psutil.disk_usage(mountpoint)
    except Exception:
        usage = psutil.disk_usage("/")

    total_gb = round(usage.total / (1024 ** 3), 2)
    used_gb = round(usage.used / (1024 ** 3), 2)
    free_gb = round(usage.free / (1024 ** 3), 2)
    
    # Determinar Tipo SSD/HDD (estimación básica por nombre/plataforma)
    disk_type = detect_disk_type(device, mountpoint)
    
    # IOPS Simulado (acorde a lo permitido en los requerimientos de la práctica)
    simulated_iops = random.randint(800, 3500) if disk_type == "SSD" else random.randint(100, 500)
    
    return {
        "name": device or mountpoint,
        "mountpoint": mountpoint,
        "type": disk_type,
        "total_gb": total_gb,
        "used_gb": used_gb,
        "free_gb": free_gb,
        "iops": simulated_iops,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

if __name__ == "__main__":
    print("--- Prueba de Extracción de Métricas de Disco (Tanina) ---")
    metrics = get_first_disk_metrics()
    print(metrics)
