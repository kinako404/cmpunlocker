import glob
import logging
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from payload.driver import (
    aggressive_unload, flr_reset, load_module, stop_display_manager, unload_modules,
)
from payload.gsp_patch import patch_gsp
from payload.build import build as build_payload

log = logging.getLogger(__name__)

_GSP_GLOB = "/lib/firmware/nvidia/*/gsp_tu10x.bin"


def _find_gsp() -> str:
    paths = sorted(glob.glob(_GSP_GLOB), reverse=True)
    if not paths:
        raise FileNotFoundError(f"No GSP firmware found matching {_GSP_GLOB}")
    return paths[0]


def run_full_unlock(pci_full: str, gsp_path: str = None) -> bool:
    if gsp_path is None:
        gsp_path = _find_gsp()

    backup_path = gsp_path + ".cmpunlocker.bak"
    patched_path = gsp_path + ".cmpunlocker.patched"

    log.info("[%s] Starting full unlock pipeline", pci_full)
    log.info("[%s] GSP firmware: %s", pci_full, gsp_path)

    log.info("[%s] Stopping display manager and unloading modules", pci_full)
    stop_display_manager()
    unload_modules()

    if not os.path.exists(backup_path):
        shutil.copy2(gsp_path, backup_path)
        log.info("[%s] GSP backup written to %s", pci_full, backup_path)

    log.info("[%s] Building ROP payload", pci_full)
    payload = build_payload()

    log.info("[%s] Injecting payload into GSP firmware", pci_full)
    patch_gsp(backup_path, payload, patched_path)
    shutil.copy2(patched_path, gsp_path)

    log.info("[%s] Loading patched driver", pci_full)
    load_module()
    time.sleep(5)

    log.info("[%s] FLR reset #1", pci_full)
    flr_reset(pci_full)

    log.info("[%s] Aggressive driver unload", pci_full)
    aggressive_unload()

    log.info("[%s] FLR reset #2", pci_full)
    flr_reset(pci_full)

    from unlock.compute import apply_unlock
    from unlock.vram import apply_vram_unlock

    log.info("[%s] Applying compute unlock", pci_full)
    ok_compute, msg_compute = apply_unlock(pci_full)
    if ok_compute:
        log.info("[%s] Compute unlock succeeded", pci_full)
    else:
        log.warning("[%s] Compute unlock: %s", pci_full, msg_compute)

    log.info("[%s] Applying VRAM unlock", pci_full)
    ok_vram, msg_vram = apply_vram_unlock(pci_full)
    if ok_vram:
        log.info("[%s] VRAM unlock succeeded — %s", pci_full, msg_vram)
    else:
        log.warning("[%s] VRAM unlock: %s", pci_full, msg_vram)

    ok = ok_compute and ok_vram

    log.info("[%s] Restoring original GSP firmware", pci_full)
    shutil.copy2(backup_path, gsp_path)

    log.info("[%s] Reloading driver", pci_full)
    load_module()
    time.sleep(3)

    log.info("[%s] Pipeline complete — ok=%s", pci_full, ok)
    return ok


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    pci = sys.argv[1] if len(sys.argv) > 1 else None
    gsp = sys.argv[2] if len(sys.argv) > 2 else None
    if pci is None:
        from payload.gpu import find_gpu
        pci = find_gpu()
        if pci is None:
            print("ERROR: No compatible GPU found")
            sys.exit(1)
    run_full_unlock(pci, gsp)


if __name__ == "__main__":
    main()
