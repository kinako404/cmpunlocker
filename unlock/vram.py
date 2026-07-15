import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from payload.bar0 import Bar0
from common.constants import get


def get_vram_target(target_key: str = None) -> tuple:
    """Resolve VRAM target address and value from constants.yaml.

    Returns (addr, value) or (None, None) if not configured.
    """
    if target_key is None:
        target_key = get('vram_config.fb_ctrl.default_target', 'unlocked_40gb')
    addr = get('vram_config.fb_ctrl.addr')
    value = get(f'vram_config.fb_ctrl.values.{target_key}')
    return addr, value


def get_refresh_tuning() -> tuple:
    """Resolve refresh-interval tuning address and value.

    Returns (addr, value) or (None, None) if not configured.
    """
    addr = get('vram_config.refresh_interval.addr')
    value = get('vram_config.refresh_interval.value')
    return addr, value


def is_vram_unlocked(pci_full: str, target_key: str = None) -> bool:
    """Check if the HBM2 memory configuration matches the target capacity."""
    addr, value = get_vram_target(target_key)
    if addr is None or value is None:
        return False
    with Bar0(pci_full) as bar0:
        return bar0.rd32(addr) == value


def get_vram_current(pci_full: str) -> int:
    """Read the current value of the HBM2 memory configuration register."""
    addr = get('vram_config.fb_ctrl.addr')
    if addr is None:
        raise RuntimeError("vram_config.fb_ctrl.addr not configured")
    with Bar0(pci_full) as bar0:
        return bar0.rd32(addr)


def apply_vram_unlock(pci_full: str, target_key: str = None) -> tuple:
    """Write the HBM2 memory configuration override via BAR0.

    The register is only writable after the PLM has been opened by the HS-mode
    ROP chain (payload/build.py). The override persists across FLR.

    Returns (success: bool, message: str).
    """
    addr, value = get_vram_target(target_key)
    if addr is None or value is None:
        return False, "VRAM target not configured in constants.yaml"

    with Bar0(pci_full) as bar0:
        current = bar0.rd32(addr)
        if current == value:
            return True, f"VRAM already at target (0x{value:08X})"

        bar0.wr32(addr, value)
        actual = bar0.rd32(addr)
        if actual != value:
            return False, f"VRAM write failed: wrote 0x{value:08X}, read 0x{actual:08X}"

    # Optionally apply refresh-interval tuning for 80GB stability on binned cards.
    refresh_addr, refresh_value = get_refresh_tuning()
    if refresh_addr is not None and refresh_value is not None:
        with Bar0(pci_full) as bar0:
            bar0.wr32(refresh_addr, refresh_value)
            actual_refresh = bar0.rd32(refresh_addr)
            refresh_ok = actual_refresh == refresh_value
        if refresh_ok:
            return True, f"VRAM unlocked to 0x{value:08X} + refresh tuning applied"
        else:
            return True, f"VRAM unlocked to 0x{value:08X} (refresh tuning failed)"

    return True, f"VRAM unlocked to 0x{value:08X}"
