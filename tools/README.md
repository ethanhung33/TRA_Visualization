# tools/ — 自動化鷹架

讓 Claude 能在無人監督下新增鐵路系統並自我除錯的兩支工具。完整流程見 `.claude/skills/new-system/SKILL.md`（或對 Claude 說 `/new-system`）。

## validate_system.py — 資料契約驗證器

檢查一個系統目錄是否符合前端 `main.js` 真正讀取的格式（拓樸/設定/時刻表的交叉引用、`t`/`v` 陣列長度、view_preset 引用等）。是自動化流程的「機器回饋」來源。

```
py tools/validate_system.py data/Taiwan/TRA                  # 抽查 2 個時刻表檔
py tools/validate_system.py data/Japan/Nankai --timetable-sample 0   # 全量檢查
```

- 退出碼 0 = 無 ERROR（可能有 WARNING），1 = 有 ERROR，2 = 檔案問題。
- **ERROR** = 前端會壞，必修。**WARNING** = 渲染不完整但可運作（如拓樸外車站、缺色車種）。
- **全站覆蓋檢查**：用 `--timetable-sample 0`（檢查全部時刻表檔）時，會驗證拓樸中每站是否都有列車停靠；有空站會列出（多半是站名對照漏掉，如 navitime 的 `〔京阪線〕` 後綴）。抽查模式不做此檢查以免誤報。

## screenshot.py — 視覺除錯（給 Claude 一雙眼睛）

自起臨時 HTTP server、headless Chromium 載入 `index.html`、呼叫前端 `init()` 載入指定系統、截圖成 PNG，Claude 再用 Read 工具「看」結果。會印出 console 錯誤與頁面例外。

```
py tools/screenshot.py --init data/Taiwan/TRA/ --out shots/tra.png --wait 3500
py tools/screenshot.py --init data/Japan/Nankai/ --click "南海本線" --out shots/nankai.png
```

首次需安裝瀏覽器：`py -m playwright install chromium`（playwright 套件已安裝）。
截圖輸出在 `shots/`（已 gitignore）。
