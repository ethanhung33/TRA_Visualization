#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screenshot.py — 給 Claude 一雙眼睛：自動開啟視覺化界面並截圖

讓步驟 6（開 localhost 視覺 debug）變成可閉環的自動流程：
本腳本會在 repo 根目錄起一個臨時 HTTP server、用 headless Chromium 載入 index.html、
直接呼叫前端的 init(systemPath) 載入指定系統，等畫面渲染後截圖成 PNG，Claude 再讀取該 PNG「看」結果。

需求: pip/playwright 已安裝；首次需 `py -m playwright install chromium`

用法:
    # 載入某系統並截圖
    py tools/screenshot.py --init data/Taiwan/TRA/ --out shots/tra.png --wait 2500

    # 載入系統、再點某個 view preset 按鈕（用文字比對）後截圖
    py tools/screenshot.py --init data/Japan/Nankai/ --click "南海本線" --out shots/nankai.png

    # 載入後執行任意 JS（進階偵錯），再截圖
    py tools/screenshot.py --init data/Taiwan/HSR/ --eval "selectAllTrains && selectAllTrains()" --out shots/hsr.png

也會把 console 錯誤與頁面例外印到 stdout，方便 Claude 偵錯（例如 init 失敗、JSON 載入錯誤）。
"""
import sys
import os
import time
import argparse
import threading
import functools
import http.server
import socketserver
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent


def start_server(root, port=0):
    """在 root 目錄起一個安靜的 HTTP server，回傳 (httpd, port, thread)。port=0 自動挑空閒埠。"""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    actual_port = httpd.server_address[1]
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    return httpd, actual_port, th


def main():
    ap = argparse.ArgumentParser(description="自動載入視覺化界面並截圖")
    ap.add_argument("--init", help="要載入的系統路徑（傳給前端 init()），如 data/Taiwan/TRA/")
    ap.add_argument("--click", action="append", default=[],
                    help="載入後要點擊的按鈕文字（可重複），用於選 view preset")
    ap.add_argument("--eval", dest="eval_js", help="載入後在頁面執行的任意 JS")
    ap.add_argument("--out", default="shots/screenshot.png", help="輸出 PNG 路徑")
    ap.add_argument("--wait", type=int, default=2500, help="init 後等待渲染的毫秒數")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=1000)
    ap.add_argument("--port", type=int, default=0, help="HTTP server 埠（0=自動）")
    ap.add_argument("--headed", action="store_true", help="顯示瀏覽器視窗（預設 headless）")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ 未安裝 playwright。請執行: py -m pip install playwright && py -m playwright install chromium",
              file=sys.stderr)
        sys.exit(2)

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    httpd, port, _ = start_server(REPO_ROOT, args.port)
    base = f"http://127.0.0.1:{port}/index.html"
    print(f"🌐 本地服務啟動於 {base}")

    console_errors = []
    page_errors = []
    exit_code = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not args.headed)
            page = browser.new_page(viewport={"width": args.width, "height": args.height})
            page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: page_errors.append(str(e)))

            page.goto(base, wait_until="networkidle")

            if args.init:
                init_path = args.init if args.init.endswith("/") else args.init + "/"
                print(f"▶️  載入系統 '{init_path}'（複製首頁按鈕的切換流程）")
                # 忠實複製 main.js 首頁按鈕的 onclick：隱藏 landing、顯示 app、呼叫 init
                page.evaluate(
                    """async (path) => {
                        if (typeof init !== 'function') throw new Error('找不到全域 init() 函式');
                        const landing = document.getElementById('landing-page');
                        const app = document.getElementById('app');
                        if (landing) landing.style.display = 'none';
                        if (app) app.style.display = 'flex';
                        await init(path);
                    }""",
                    init_path,
                )

            page.wait_for_timeout(args.wait)

            for label in args.click:
                # 以文字比對找按鈕（view preset 按鈕為動態產生）
                btn = page.locator(f"button:has-text('{label}'), .pill-btn:has-text('{label}')").first
                if btn.count() > 0:
                    print(f"🖱️  點擊按鈕: {label}")
                    btn.click()
                    page.wait_for_timeout(args.wait)
                else:
                    print(f"⚠️  找不到按鈕文字: {label}")

            if args.eval_js:
                print(f"🧪 執行 JS: {args.eval_js}")
                page.evaluate(args.eval_js)
                page.wait_for_timeout(args.wait)

            page.screenshot(path=str(out_path), full_page=False)
            print(f"📸 已截圖 -> {out_path}")

            browser.close()
    except Exception as e:
        print(f"❌ 截圖流程失敗: {e}", file=sys.stderr)
        exit_code = 1
    finally:
        httpd.shutdown()

    if console_errors:
        print(f"\n🔴 Console 錯誤 ({len(console_errors)}):")
        for m in console_errors[:20]:
            print(f"   - {m}")
    if page_errors:
        print(f"\n🔴 頁面例外 ({len(page_errors)}):")
        for m in page_errors[:20]:
            print(f"   - {m}")
    if not console_errors and not page_errors and exit_code == 0:
        print("✅ 無 console 錯誤或頁面例外")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
