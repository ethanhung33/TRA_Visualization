"""
navitime_http.py — navitime 爬蟲共用的自適應節流請求

navitime 對短時間大量請求會回 403（有時 429），持續撞會被暫時封鎖 IP 十幾分鐘，
連 stationList 都抓不到。以前各爬蟲寫死 --workers/--sleep：設快了被擋、被擋的請求
重試 3 次（間隔 3 秒）就丟掉（叡電缺整段、阪急少 12% 都是這樣來的）；設慢了又白等。

本模組讓「所有線程共用同一個節流器」：
- 請求開始時刻之間至少間隔 interval 秒（多線程只用來重疊等待回應的時間，不會加快請求頻率）
- 每次成功 → interval 乘 SPEEDUP 慢慢加快，但不低於 floor
- 403/429 → interval 加倍、全體暫停冷卻（60s → 180s → 600s → 900s），
  並把 floor 提高到「被擋時的間隔 × 1.2」，之後不會再試探到會被擋的速度
- 冷卻後重試同一個請求，不丟掉；冷卻全部用完仍被擋才放棄並計入失敗原因
- 400/404 等其他 4xx 是確定性錯誤（例如 stops 頁 node 無效），不重試

用法（各路線 script/timetable.py）：
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools"))
    import navitime_http
    def get_soup(url, retries=3):
        return navitime_http.get_soup(url, SESSION, FAIL_REASONS, start_interval=SLEEP, retries=retries)
進度訊息可附上 navitime_http.status() 顯示目前間隔與冷卻次數。
"""
import threading
import time

import requests
from bs4 import BeautifulSoup

MIN_FLOOR = 1.2                     # 絕對下限（秒）；實測 ~2 req/s 會被擋、~0.5 req/s 穩定
SPEEDUP = 0.98                      # 每次成功後 interval 乘上此值
MAX_INTERVAL = 30.0
COOLDOWNS = (60, 180, 600, 900)     # 連續被擋時依序冷卻的秒數
BLOCK_STATUS = (403, 429)


class AdaptiveThrottle:
    def __init__(self):
        self._lock = threading.Lock()
        self.interval = None        # 第一次請求時由 start_interval 初始化
        self.floor = MIN_FLOOR
        self._next_slot = 0.0       # 下一個請求最早可開始的時刻
        self._block_level = 0       # 目前連續冷卻到第幾級
        self._last_block_end = 0.0  # 最近一次冷卻結束的時刻
        self.blocks = 0             # 本次執行累計被擋次數
        self.aborted = False        # 冷卻用完 → 其餘排隊中的請求立即退出

    def wait(self, start_interval):
        """排隊取得下一個請求時段並睡到該時刻，回傳實際開始時刻。
        睡醒時若期間發生了冷卻（時段落在冷卻結束前），重新排隊，冷卻期間不送任何請求。"""
        while True:
            if self.aborted:
                raise SystemExit(1)
            with self._lock:
                if self.interval is None:
                    self.interval = max(start_interval, self.floor)
                now = time.monotonic()
                slot = max(now, self._next_slot)
                self._next_slot = slot + self.interval
            if slot > now:
                time.sleep(slot - now)
            with self._lock:
                if slot >= self._last_block_end:
                    return slot

    def ok(self):
        with self._lock:
            self.interval = max(self.floor, self.interval * SPEEDUP)
            self._block_level = 0

    def blocked(self, started_at, status):
        """回報被擋並安排冷卻。只有在最近一次冷卻結束後才發出的請求才算新證據、才升級冷卻，
        避免多線程同一波 403 被重複計算。
        冷卻全部用完仍被擋 → 中止整次執行（SystemExit(1)），不留下缺一大塊的殘缺資料；
        從 worker 線程拋出時，主線程的 future.result() 會再拋出，一樣會中止。"""
        with self._lock:
            if started_at < self._last_block_end:
                return          # 這個請求是冷卻前發出的舊請求，已經處理過
            if self._block_level >= len(COOLDOWNS):
                total = sum(COOLDOWNS) // 60
                if not self.aborted:
                    print(f"   ❌ HTTP {status}：累計冷卻 {total} 分鐘仍被 navitime 封鎖，中止（不寫檔）", flush=True)
                self.aborted = True
                raise SystemExit(1)
            cooldown = COOLDOWNS[self._block_level]
            self._block_level += 1
            self.blocks += 1
            old = self.interval
            self.floor = min(MAX_INTERVAL, max(self.floor, old * 1.2))
            self.interval = min(MAX_INTERVAL, max(self.floor, old * 2))
            now = time.monotonic()
            self._last_block_end = now + cooldown
            self._next_slot = max(self._next_slot, self._last_block_end)
            print(f"   ⏸️  HTTP {status}：全體冷卻 {cooldown} 秒；間隔 {old:.1f}→{self.interval:.1f} 秒"
                  f"（下限升為 {self.floor:.1f} 秒）", flush=True)

    def status(self):
        if self.interval is None:
            return "間隔 -"
        s = f"間隔 {self.interval:.1f}s"
        if self.blocks:
            s += f"、被擋 {self.blocks} 次"
        return s


THROTTLE = AdaptiveThrottle()


def status():
    return THROTTLE.status()


def get_soup(url, session, fail_reasons=None, start_interval=2.0, retries=3, timeout=20):
    """GET url 並回傳 BeautifulSoup；失敗回傳 None 並把原因計入 fail_reasons（Counter）。
    - 403/429：交給節流器冷卻後重試；冷卻用完則中止整次執行
    - timeout / 連線錯誤 / 5xx：最多重試 retries 次
    - 其他 4xx：不重試"""
    transient_left = retries
    while True:
        started = THROTTLE.wait(start_interval)
        try:
            r = session.get(url, timeout=timeout)
        except requests.exceptions.Timeout:
            reason = "timeout"
        except requests.exceptions.ConnectionError:
            reason = "connection_error"
        except Exception as e:
            reason = type(e).__name__
        else:
            if r.status_code in BLOCK_STATUS:
                THROTTLE.blocked(started, r.status_code)
                continue
            if r.status_code < 400:
                THROTTLE.ok()
                return BeautifulSoup(r.text, "html.parser")
            reason = f"HTTP {r.status_code}"
            if r.status_code < 500:
                transient_left = 0      # 確定性錯誤（如 stops 頁 node 無效回 400），不重試

        transient_left -= 1
        if transient_left > 0:
            time.sleep(3)
            continue
        if fail_reasons is not None:
            fail_reasons[reason] += 1
        return None
