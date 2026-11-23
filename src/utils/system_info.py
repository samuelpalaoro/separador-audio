"""System resources inspector: GPU, CPU, and RAM."""
import os
import torch


def get_system_hardware_info() -> dict:
    """Detect available hardware (GPU/CUDA, CPU cores, RAM)."""
    info = {
        "device": "cpu",
        "device_name": "CPU",
        "cuda_available": False,
        "vram_gb": 0.0,
        "cpu_count": os.cpu_count() or 1,
        "ram_total_gb": 0.0,
        "ram_available_gb": 0.0,
        "warning": None
    }
    
    # Check CUDA GPU
    try:
        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["device"] = "cuda"
            info["device_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["vram_gb"] = round(props.total_memory / (1024 ** 3), 2)
    except Exception:
        pass
    
    # Read system RAM from /proc/meminfo if on Linux
    try:
        if os.path.exists("/proc/meminfo"):
            mem_data = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val_kb = parts[1].strip().split()[0]
                        mem_data[key] = int(val_kb)
            
            if "MemTotal" in mem_data:
                info["ram_total_gb"] = round(mem_data["MemTotal"] / (1024 ** 2), 2)
            if "MemAvailable" in mem_data:
                info["ram_available_gb"] = round(mem_data["MemAvailable"] / (1024 ** 2), 2)
    except Exception:
        pass
    
    # Check memory warning
    if info["ram_available_gb"] > 0 and info["ram_available_gb"] < 2.0:
        info["warning"] = "Memória RAM disponível baixa (< 2 GB). A separação de faixas longas pode ser lenta."
    elif not info["cuda_available"]:
        info["warning"] = "Nenhuma GPU NVIDIA com CUDA detectada. O processamento será realizado na CPU."
        
    return info
