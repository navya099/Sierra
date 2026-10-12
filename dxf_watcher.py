"""CAD-independent, read-only DXF watcher for railway vertical profiles.

Run alongside dxf_reader.py and profile_calculator.py.
Uses polling + SHA-256 (no watchdog dependency), stable-file checks,
retry on incomplete CAD saves, and atomic CSV replacement.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from dxf_reader import ProfilePoint, extract_profile, export_csv as export_vip_csv
from profile_calculator import StationResult, calculate_stations, export_csv as export_station_csv


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_csv_write(rows, destination: Path, writer: Callable) -> None:
    """Write beside destination then replace it, keeping prior CSV on errors."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f'.{destination.stem}_', suffix='.csv', dir=destination.parent)
    os.close(fd)
    try:
        writer(rows, temp_name)
        os.replace(temp_name, destination)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


class DXFWatcher:
    def __init__(
        self,
        dxf_path: str | Path,
        interval: float = 25.0,
        poll_seconds: float = 0.5,
        stable_seconds: float = 0.6,
        vip_csv: str | Path | None = None,
        station_csv: str | Path | None = None,
        on_update: Callable[[list[ProfilePoint], list[StationResult]], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ):
        self.dxf_path = Path(dxf_path).resolve()
        if interval <= 0 or poll_seconds <= 0 or stable_seconds <= 0:
            raise ValueError('간격과 감시 주기는 모두 양수여야 합니다.')
        self.interval = interval
        self.poll_seconds = poll_seconds
        self.stable_seconds = stable_seconds
        self.vip_csv = Path(vip_csv).resolve() if vip_csv else self.dxf_path.with_name('plan_profile_result.csv')
        self.station_csv = Path(station_csv).resolve() if station_csv else self.dxf_path.with_name('profile_station_result.csv')
        if len({self.dxf_path, self.vip_csv, self.station_csv}) != 3:
            raise ValueError('입력 DXF와 두 CSV 경로는 서로 달라야 합니다.')
        self.on_update = on_update
        self.on_error = on_error
        self.last_hash: str | None = None
        self.last_signature: tuple | None = None
        self._candidate_hash: str | None = None
        self._candidate_since: float = 0.0
        self._last_error: str | None = None

    def check_once(self) -> bool:
        """Return True when calculation outputs were successfully updated."""
        now = time.monotonic()
        try:
            digest = sha256_file(self.dxf_path)
        except OSError as exc:
            self._report_error(exc)
            return False

        if digest == self.last_hash:
            self._candidate_hash = None
            self._last_error = None
            return False

        if digest != self._candidate_hash:
            self._candidate_hash = digest
            self._candidate_since = now
            return False
        if now - self._candidate_since < self.stable_seconds:
            return False

        try:
            # Guard against file replacement while the DXF is being parsed.
            vip = extract_profile(self.dxf_path)
            stations = calculate_stations(self.dxf_path, interval=self.interval)
            if sha256_file(self.dxf_path) != digest:
                self._candidate_hash = None
                return False

            signature = (
                tuple((p.kind, p.sta, p.elevation, p.gradient_in, p.gradient_out) for p in vip),
                tuple((r.sta, r.ground_el, r.plan_el, r.difference, r.gradient_permille) for r in stations),
            )
            if signature != self.last_signature:
                atomic_csv_write(vip, self.vip_csv, export_vip_csv)
                atomic_csv_write(stations, self.station_csv, export_station_csv)
                self.last_signature = signature
                if self.on_update:
                    self.on_update(vip, stations)
            self.last_hash = digest
            self._candidate_hash = None
            self._last_error = None
            return True
        except Exception as exc:
            # Keep last valid results; retry even if CAD produces no more events.
            self._report_error(exc)
            return False

    def _report_error(self, exc: Exception) -> None:
        message = f'{type(exc).__name__}: {exc}'
        if message != self._last_error:
            self._last_error = message
            if self.on_error:
                self.on_error(exc)
            else:
                print(f'[대기/오류] {message}', flush=True)

    def run(self, stop_event: threading.Event | None = None) -> None:
        stop_event = stop_event or threading.Event()
        print(f'[감시 시작] {self.dxf_path}', flush=True)
        print(f'[출력] {self.vip_csv} / {self.station_csv}', flush=True)
        while not stop_event.is_set():
            self.check_once()
            stop_event.wait(self.poll_seconds)


def print_update(vip: list[ProfilePoint], stations: list[StationResult]) -> None:
    print(f'\n[갱신 완료] VIP {len(vip)}개 / 측점 {len(stations)}개', flush=True)
    print(f'{"구분":<8} {"STA":>10} {"EL":>10} {"진입(‰)":>11} {"진출(‰)":>11}')
    for p in vip:
        incoming = '—' if p.gradient_in is None else f'{p.gradient_in:+.3f}'
        outgoing = '—' if p.gradient_out is None else f'{p.gradient_out:+.3f}'
        print(f'{p.kind:<8} {p.sta:10.3f} {p.elevation:10.3f} {incoming:>11} {outgoing:>11}')
    print(flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description='CAD DXF 저장 감지 및 종단 자동 계산')
    parser.add_argument('dxf', type=Path, help='converted_dxf.dxf 경로')
    parser.add_argument('--interval', type=float, default=25.0, help='증분측점 간격(m)')
    parser.add_argument('--poll', type=float, default=0.5, help='감시 주기(초)')
    parser.add_argument('--stable', type=float, default=0.6, help='저장 안정화 대기(초)')
    parser.add_argument('--vip-csv', type=Path, help='VIP CSV 출력 경로')
    parser.add_argument('--station-csv', type=Path, help='증분측점 CSV 출력 경로')
    args = parser.parse_args()
    watcher = DXFWatcher(
        args.dxf, interval=args.interval, poll_seconds=args.poll,
        stable_seconds=args.stable, vip_csv=args.vip_csv,
        station_csv=args.station_csv, on_update=print_update,
    )
    try:
        watcher.run()
    except KeyboardInterrupt:
        print('\n[감시 종료]')


if __name__ == '__main__':
    main()
