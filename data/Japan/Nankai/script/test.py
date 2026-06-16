import pandas as pd
import requests
from io import StringIO

url = "https://ja.wikipedia.org/wiki/南海高野線"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

print(f"🕵️ 正在診斷網頁結構: {url}\n")

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))

    for i, df in enumerate(tables):
        # 模擬你原本的表頭壓平邏輯
        original_cols = df.columns
        flattened_cols = ['_'.join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col) for col in df.columns]
        
        print(f"=== 表格 Index: {i} ===")
        print(f"原始尺寸: {df.shape}")
        print(f"壓平後的欄位: {flattened_cols}")
        
        # 印出前兩列資料，看看里程數到底躲在哪一欄
        if not df.empty:
            print("資料預覽 (前 2 列):")
            # 這裡我們看前兩列就好
            print(df.head(2).to_string(index=False, header=False))
        
        print("-" * 50)

except Exception as e:
    print(f"❌ 診斷失敗: {e}")