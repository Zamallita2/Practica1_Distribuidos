import os
import sys
import time
import platform
import random
import psutil
import subprocess

def detect_disk_type(device, mountpoint):
    """Detecta el tipo de disco (SSD/HDD) de forma multiplataforma."""
    system = platform.system()
    if system == "Windows":
        try:
            drive = os.path.splitdrive(mountpoint)[0].replace(":", "")
            command = [
                "powershell", "-NoProfile", "-Command",
                f"(Get-Partition -DriveLetter '{drive}' | Get-Disk | Get-PhysicalDisk).MediaType"
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=3)
            media_type = result.stdout.strip().upper()
            if "SSD" in media_type: return "SSD"
            if "HDD" in media_type: return "HDD"
        except Exception:
            pass
    elif system == "Linux":
        try:
            result = subprocess.run(["lsblk", "-ndo", "ROTA", device], capture_output=True, text=True, timeout=3)
            rota = result.stdout.strip()
            if rota == "0": return "SSD"
            if rota == "1": return "HDD"
        except Exception:
            pass

    # Fallback inteligente si no detecta por comando
    dev_lower = device.lower()
    if "nvme" in dev_lower or "ssd" in dev_lower:
        return "SSD"
    return "HDD" if "sd" in dev_lower or "hd" in dev_lower else "SSD"

def get_all_disks_metrics():
    """
    Detecta automáticamente TODOS los discos/particiones reales del sistema (incluyendo USBs/discos externos).
    Retorna la lista de métricas de todos los discos y destaca el primero (Requisito de la práctica).
    """
    disks_list = []
    partitions = psutil.disk_partitions(all=False)
    
    seen_devices = set()

    for part in partitions:
        mountpoint = part.mountpoint
        device = part.device

        # Evitar duplicados por puntos de montaje secundarios
        if device in seen_devices:
            continue
        seen_devices.add(device)

        try:
            usage = psutil.disk_usage(mountpoint)
            total_gb = round(usage.total / (1024 ** 3), 2)
            # Descartar particiones vacías o muy pequeñas (< 1GB) salvo dev loop
            if total_gb < 1.0:
                continue

            used_gb = round(usage.used / (1024 ** 3), 2)
            free_gb = round(usage.free / (1024 ** 3), 2)
            disk_type = detect_disk_type(device, mountpoint)
            simulated_iops = random.randint(1200, 4500) if disk_type == "SSD" else random.randint(150, 600)

            disks_list.append({
                "name": device or mountpoint,
                "mountpoint": mountpoint,
                "type": disk_type,
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "iops": simulated_iops,
                "fstype": part.fstype
            })
        except Exception:
            continue

    return disks_list

def get_first_disk_metrics():
    """
    Mantiene compatibilidad retornando las métricas del PRIMER disco detectado,
    e incluye la lista de 'all_disks' para detección dinámica de USBs / discos múltiples.
    """
    all_disks = get_all_disks_metrics()
    if not all_disks:
        # Fallback de emergencia
        return {
            "name": "/dev/sda1",
            "mountpoint": "/",
            "type": "SSD",
            "total_gb": 100.0,
            "used_gb": 50.0,
            "free_gb": 50.0,
            "iops": 2000,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "all_disks": []
        }

    first = all_disks[0].copy()
    first["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    first["all_disks"] = all_disks
    return first

if __name__ == "__main__":
    print("--- Prueba de Extracción de Todos los Discos y USBs ---")
    metrics = get_first_disk_metrics()
    print("Primer disco:", metrics)
    print("Todos los discos detectados:", metrics.get("all_disks"))
