import struct
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.constants import get

# Base writes that run inside the HS-mode ROP chain.
# The VRAM config write (0x009A0204) is injected from constants.yaml so the
# target capacity can be changed without editing code.
_BASE_WRITES = [
    (0x00100CE0, 0x0000020B),
    (0x00823804, 0xFFFFFFFF),
]


def _get_writes() -> list:
    """Assemble the BAR0 writes for the ROP payload.

    The first write sets the HBM2 memory configuration broadcast register.
    The target capacity is read from constants.yaml (vram_config.default_target).
    """
    vram_addr = get('vram_config.fb_ctrl.addr')
    vram_target_key = get('vram_config.fb_ctrl.default_target', 'unlocked_40gb')
    vram_value = get(f'vram_config.fb_ctrl.values.{vram_target_key}')

    writes = []
    if vram_addr is not None and vram_value is not None:
        writes.append((vram_addr, vram_value))
    writes.extend(_BASE_WRITES)
    return writes


def build() -> bytes:
    payload_size = get('dmem_layout.payload_size')
    dma_target = get('dmem_layout.dma_target')
    canary = get('dmem_layout.canary')
    canary_addr = get('dmem_layout.guard_addr')
    frame_start = get('payload_frames.frame_start_addr')
    frame_stride = get('payload_frames.frame_stride')
    gadget_addr = get('booter_addrs.bar0_write_gadget')
    tail_return = 0x0000810D

    payload = bytearray(payload_size)

    def w32(dmem_addr: int, val: int) -> None:
        off = dmem_addr - dma_target
        if 0 <= off <= len(payload) - 4:
            struct.pack_into("<I", payload, off, val & 0xFFFFFFFF)

    w32(canary_addr, canary)

    a = frame_start
    for addr, val in _get_writes():
        w32(a + get('payload_frames.frame_field_offsets.r0'), canary_addr)
        w32(a + get('payload_frames.frame_field_offsets.r1'), 0x00000000)
        w32(a + get('payload_frames.frame_field_offsets.r2'), val)
        w32(a + get('payload_frames.frame_field_offsets.r3'), addr)
        w32(a + get('payload_frames.frame_field_offsets.saved_reg'), canary)
        w32(a + get('payload_frames.frame_field_offsets.return_addr'), gadget_addr)
        a += frame_stride

    w32(a + get('payload_frames.frame_field_offsets.r0'), 0x00000000)
    w32(a + get('payload_frames.frame_field_offsets.r1'), 0x00000000)
    w32(a + get('payload_frames.frame_field_offsets.r2'), 0x00000000)
    w32(a + get('payload_frames.frame_field_offsets.r3'), 0x00000000)
    w32(a + get('payload_frames.frame_field_offsets.saved_reg'), canary)
    w32(a + get('payload_frames.frame_field_offsets.return_addr'), tail_return)

    return bytes(payload)
