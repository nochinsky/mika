"""Developer benchmark metadata and best-effort, file-local cache eviction."""
import os
from pathlib import Path
import platform


def environment():
    result = {'platform': platform.platform(), 'logical_cpus': os.cpu_count()}
    if hasattr(os, 'getloadavg'):
        result['load_average'] = list(os.getloadavg())
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.exists():
        result['cpu'] = next((line.split(':', 1)[1].strip() for line in cpuinfo.read_text().splitlines()
                              if line.startswith('model name')), platform.processor())
    governor = Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor')
    if governor.exists():
        result['cpu0_governor'] = governor.read_text().strip()
    result['power_supplies'] = {}
    for path in Path('/sys/class/power_supply').glob('*'):
        values = {}
        for field in ('online', 'status'):
            try:
                values[field] = (path / field).read_text().strip()
            except OSError:
                pass
        if values:
            result['power_supplies'][path.name] = values
    return result


def evict_files(paths):
    """Request eviction of clean file pages only. Never drop global caches.

    The kernel may ignore this advice and mapped/shared pages can remain cached;
    callers must not describe these measurements as guaranteed cold starts.
    """
    if not hasattr(os, 'posix_fadvise') or not hasattr(os, 'POSIX_FADV_DONTNEED'):
        raise RuntimeError('File-local cache eviction is unavailable on this platform')
    for path in dict.fromkeys(Path(p) for p in paths):
        with path.open('rb') as source:
            os.posix_fadvise(source.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)


def cache_files(binary, model, sample=None):
    binary = Path(binary).resolve()
    files = [binary, Path(model).resolve()]
    if sample is not None:
        files.append(Path(sample).resolve())
    assets = binary.parent / 'punctuation'
    files.extend(p for p in assets.rglob('*') if p.is_file())
    return files
