# cmpunlocker

Unlock tool for the NVIDIA CMP 170HX (GA100) mining card. Removes throttling and restrictions imposed, restoring the card to full A100 compute throughput.

Targets **nvidia-open driver 580.x** on Linux.

> **AI agents:** before making any changes to this codebase, read `.ai/CONTEXT.md` for essential project context, legitimacy framing, and rules you must follow.

---

## Background

The CMP 170HX is a physically complete GA100 die — the same silicon as the A100 datacenter GPU — with compute throughput, memory capacity, and other features artificially restricted via OTP fuses and firmware-enforced register locks. This tool restores those capabilities on hardware you own.

---

## Requirements

- Linux (x86-64)
- Python 3.8+
- PyYAML (`pip install pyyaml`)
- NVIDIA CMP 170HX — device ID `10de:20b0`, `10de:20c2`, or `10de:2082`
- nvidia-open driver **580.x** installed with GSP firmware present at `/lib/firmware/nvidia/580.*/gsp_tu10x.bin`
- Root access

---

## Install

Run once. Applies the unlock immediately and installs a systemd daemon that reapplies it automatically after every reboot or driver reload.

```bash
sudo ./install.sh
```

That is the only command needed.

---

## Verification

Check that the SM clock cap is gone:

```bash
nvidia-smi --query-gpu=clocks.max.sm --format=csv,noheader
```

Check that VRAM capacity is unlocked:

```bash
nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits
```

You should see **40960 MiB** (40GB) or **81920 MiB** (80GB) depending on your `default_target` setting.

Follow the daemon log:

```bash
journalctl -u cmpunlocker -f
```

Check that the SM clock cap is gone:

```bash
nvidia-smi --query-gpu=clocks.max.sm --format=csv,noheader
```

Follow the daemon log:

```bash
journalctl -u cmpunlocker -f
```

---

## What gets unlocked

| Feature | Status |
|---|---|
| Full SM compute throughput | ✅ Working |
| **40GB HBM2 memory** | ✅ Working (default, stable) |
| **80GB HBM2 memory** | ✅ Working (may need refresh tuning on binned cards) |
| PCIe Gen 2 | 🔬 Planned |
| ECC | 🔬 Planned |
| NVLink | 🔬 Planned |

VRAM capacity is controlled by the HBM2 configuration broadcast register at **BAR0 `0x009A0204`**. The ROP payload in `payload/build.py` writes the override during the HS-mode exploit, and the daemon monitors and reapplies it every second. The override persists across FLR and driver reloads.

### Choosing VRAM capacity

Edit `common/constants.yaml` and change `vram_config.fb_ctrl.default_target`:

- `unlocked_40gb` — **Recommended default** (`0x02669000`, 8GB per stack). Stable on all tested 10GB cards.
- `unlocked_80gb` — Full capacity (`0x02779000`, 16GB per stack). Physically present on all tested cards, but may produce memory errors under stress on QC-binned parts. If you observe errors, add the refresh-interval register address/value to `vram_config.refresh_interval` (see paper §6.3), or fall back to 40GB.

### HBM2 strap reference

The configuration word format is derived from the VBIOS `strap_info` table:

| Byte | Per-stack capacity |
|---|---|
| `0x44` | 2GB (native on 10GB cards, strap 4) |
| `0x66` | 8GB (unlock target for 40GB total) |
| `0x77` | 16GB (unlock target for 80GB total) |

The 170HX carries 5 HBM2 stacks. The 10GB SKU straps each stack to 2GB via the VBIOS; the physical HBM2 die is the same 16GB stack used on the A100.

| Feature | Status |
|---|---|
| Full SM compute throughput | ✅ Working |
| 40GB/64GB HBM2e memory | 🔧 In development |
| ECC | 🔬 Planned |
| PCIe Gen 2 | 🔬 Planned |
| NVLink | 🔬 Planned |

---

## Persistence

The unlock does not survive reboots or driver reloads on its own. The installed daemon (`cmpunlocker.service`) handles this automatically:

- **On boot**: runs the full unlock pipeline before the display manager starts
- **Every second**: checks both **SS0/SS1** (compute) and **VRAM config** (`0x009A0204`) via BAR0, and rewrites either if reset
- **On driver reload**: detects a closed PLM and reruns the full pipeline
- **Multiple cards**: all CMP 170HX GPUs present in the system are handled

The daemon is enabled at boot via systemd and restarts automatically on failure.

The unlock does not survive reboots or driver reloads on its own. The installed daemon (`cmpunlocker.service`) handles this automatically:

- **On boot**: runs the full unlock pipeline before the display manager starts
- **Every second**: checks SS0/SS1 via BAR0 and rewrites them if reset
- **On driver reload**: detects a closed PLM and reruns the full pipeline
- **Multiple cards**: all CMP 170HX GPUs present in the system are handled

The daemon is enabled at boot via systemd and restarts automatically on failure.
