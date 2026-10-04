"""
把 GlowSans 字型裁成「本站實際用到的字」並轉成 woff2。

完整的 GlowSansSC-Compressed-Regular.otf 有 8.9 MB，GitHub Pages 不壓縮 .otf，
首頁又會等字型載完才顯示 → 一進網站就要等很久。裁切後只剩幾百 KB。

收字範圍：所有路線的 json（站名、車種、車名…）、前端程式與頁面文字、
完整 ASCII / 假名 / 全形符號（搜尋框輸入用）。

新增路線或站名後重跑一次：
    py tools/subset_font.py
需要 fonttools 與 brotli（py -m pip install fonttools brotli）。
"""
import json
import os
import sys

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'fonts', 'GlowSansSC-Compressed-Regular.otf')
OUT = os.path.join(ROOT, 'fonts', 'GlowSans-subset.woff2')

TEXT_FILES = ['main.js', 'index.html', 'style.css']
EXTRA_RANGES = [
    (0x0020, 0x007E),  # ASCII
    (0x00B7, 0x00B7),  # ·
    (0x2010, 0x2027),  # 各式破折號、引號、…
    (0x2190, 0x21FF),  # 箭頭
    (0x2460, 0x24FF),  # ①② 等圈號數字
    (0x25A0, 0x25FF),  # ■▲● 等幾何符號
    (0x3000, 0x303F),  # 中日文標點
    (0x3040, 0x30FF),  # 平假名、片假名
    (0xFF01, 0xFF5E),  # 全形英數符號
]


def collect_chars():
    chars = set()
    for lo, hi in EXTRA_RANGES:
        chars.update(chr(c) for c in range(lo, hi + 1))

    for name in TEXT_FILES:
        with open(os.path.join(ROOT, name), encoding='utf-8') as f:
            chars.update(f.read())

    data_dir = os.path.join(ROOT, 'data')
    for dirpath, _, filenames in os.walk(data_dir):
        # 只看前端會讀的 json/，略過爬蟲的原始資料
        if os.sep + 'json' not in dirpath + os.sep and dirpath != data_dir:
            continue
        for fn in filenames:
            if not fn.endswith('.json') or fn.startswith('raw_'):
                continue
            with open(os.path.join(dirpath, fn), encoding='utf-8') as f:
                # ensure_ascii=False 後的字串才看得到 \uXXXX 轉義過的字
                text = f.read()
            try:
                text = json.dumps(json.loads(text), ensure_ascii=False)
            except ValueError:
                pass
            chars.update(text)

    return {c for c in chars if c.isprintable() or c == ' '}


def main():
    chars = collect_chars()
    font = TTFont(SRC)
    cmap = font.getBestCmap()
    missing = sorted(c for c in chars if ord(c) not in cmap and ord(c) > 0x7E)

    options = subset.Options()
    options.flavor = 'woff2'
    options.layout_features = ['*']
    options.name_IDs = ['*']
    options.notdef_outline = True
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=[ord(c) for c in chars])
    subsetter.subset(font)
    font.flavor = 'woff2'
    font.save(OUT)

    print(f'{len(chars)} chars -> {OUT} ({os.path.getsize(OUT) / 1024:.0f} KB, '
          f'source {os.path.getsize(SRC) / 1024 / 1024:.1f} MB)')
    if missing:
        print(f'{len(missing)} chars not in the font (fall back to system font): '
              + ''.join(missing[:80]) + (' …' if len(missing) > 80 else ''))


if __name__ == '__main__':
    sys.exit(main())
