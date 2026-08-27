import os
import sys
import time
import platform
import random
import psutil
import subprocess

def detect_disk_type(device, mountpoint):
    """Detecta el tipo de disco (SSD/HDD/USB) de forma multiplataforma."""
    dev_lower = device.lower()
    mount_lower = mountpoint.lower()

    # Detectar si es una unidad extraíble USB por punto de montaje o dispositivo
    if "/media" in mount_lower or "/run/media" in mount_lower or "usb" in dev_lower:
        return "USB"

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
            if "USB" in media_type or "REMOVABLE" in media_type: return "USB"
            if "SSD" in media_type: return "SSD"
            if "HDD" in media_type: return "HDD"
        except Exception:
            pass
    elif system == "Linux":
        try:
            # Consultar con udevadm o lsblk si es un USB extraíble
            result = subprocess.run(["lsblk", "-ndo", "RM,ROTA", device], capture_output=True, text=True, timeout=3)
            out = result.stdout.strip().split()
            if len(out) >= 1 and out[0] == "1":
                return "USB"
            if len(out) >= 2 and out[1] == "0":
                return "SSD"
            if len(out) >= 2 and out[1] == "1":
                return "HDD"
        except Exception:
            pass

    # Fallback inteligente
    if "nvme" in dev_lower or "ssd" in dev_lower:
        return "SSD"
    return "HDD"

def get_all_disks_metrics():
    """
    Escanea activamente TODOS los discos/particiones reales del sistema (incluyendo USBs/discos externos).
    Soporta la detección en caliente de unidades agregadas o retiradas.
    """
    disks_list = []
    # Usar all=True para incluir puntos de montaje extraíbles como /media o /run/media
    partitions = psutil.disk_partitions(all=True)
    
    seen_devices = set()

    for part in partitions:
        mountpoint = part.mountpoint
        device = part.device

        # Filtrar sistemas de archivos virtuales o temporales de Linux
        fstype = part.fstype.lower()
        if fstype in ["squashfs", "tmpfs", "devtmpfs", "sysfs", "proc", "cgroup", "autofs", "pstore", "bpf", "configfs", "fusectl"]:
            continue
        if mountpoint.startswith("/snap") or mountpoint.startswith("/sys") or mountpoint.startswith("/proc") or mountpoint.startswith("/dev"):
            if not mountpoint.startswith("/dev/shm"):
                pass
            if fstype in ["squashfs", "tmpfs"]:
                continue

        # Evitar duplicados por puntos de montaje
        key = f"{device}:{mountpoint}"
        if key in seen_devices:
            continue
        seen_devices.add(key)

        try:
            usage = psutil.disk_usage(mountpoint)
            total_gb = round(usage.total / (1024 ** 3), 2)
            # Aceptar unidades mayores a 100MB (para memorias USB pequeñas)
            if total_gb < 0.1:
                continue

            used_gb = round(usage.used / (1024 ** 3), 2)
            free_gb = round(usage.free / (1024 ** 3), 2)
            disk_type = detect_disk_type(device, mountpoint)
            
            # Asignar IOPS acorde a la tecnología
            if disk_type == "SSD":
                simulated_iops = random.randint(1800, 4500)
            elif disk_type == "USB":
                simulated_iops = random.randint(300, 1200)
            else:
                simulated_iops = random.randint(150, 600)

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
    Obtiene las métricas del disco principal e incluye la lista dinámica 'all_disks'
    para la sincronización en tiempo real de USBs y múltiples unidades.
    """
    all_disks = get_all_disks_metrics()
    if not all_disks:
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
    print("--- Prueba de Escaneo Dinámico de Discos y USBs ---")
    metrics = get_first_disk_metrics()
    print("Discos detectados:", len(metrics.get("all_disks")))
    for d in metrics.get("all_disks"):
        print(" ->", d)
