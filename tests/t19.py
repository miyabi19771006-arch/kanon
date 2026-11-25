# -*- coding: utf-8 -*-
import asyncio
from playwright.async_api import async_playwright
import os, pathlib
# このテストが見にいく kanon 本体。既定はリポジトリの index.html。
# 別のファイルを試すときは KANON=/path/to/app.html python3 tests/t5.py
ROOT = pathlib.Path(__file__).resolve().parent.parent
APP  = os.environ.get("KANON", str(ROOT / "index.html"))
APPURL = "file://" + APP
OUTDIR = os.environ.get("KANON_OUT", str(ROOT / "tests" / "_shots"))
os.makedirs(OUTDIR, exist_ok=True)

ok=[];ng=[];errs=[]
def t(c,m):(ok if c else ng).append(m)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await (await b.new_context(viewport={'width':390,'height':844})).new_page()
        pg.on('pageerror',lambda e:errs.append(str(e)))
        await pg.goto(APPURL); await pg.wait_for_timeout(800)
        sts=await pg.evaluate("D.stores")
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.click('#m-ship'); await pg.wait_for_timeout(300)
        await pg.click('#sCrop .chip'); await pg.wait_for_timeout(300)
        # 未入力で保存 → 赤くなる
        await pg.click('#sSave'); await pg.wait_for_timeout(500)
        t(await pg.evaluate("$('fldSQty').classList.contains('bad')"),'未入力だと赤くなる')
        # 数字を入れたら赤が消える
        await pg.fill(f'[data-bsi="{sts[0]}"]','5'); await pg.wait_for_timeout(300)
        t(not await pg.evaluate("$('fldSQty').classList.contains('bad')"),'★入れたら赤が消える')
        t(not await pg.evaluate("$('errShip').classList.contains('on')"),'赤帯も消える')
        # ＋でも消える
        await pg.click('#sSave'); await pg.wait_for_timeout(400)
        await pg.evaluate("()=>{shipQty={};renderShipRows()}")
        await pg.click('#sSave'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("$('fldSQty').classList.contains('bad')"),'もう一度赤くなる')
        await pg.click(f'[data-bsq="{sts[1]}"][data-d="1"]'); await pg.wait_for_timeout(300)
        t(not await pg.evaluate("$('fldSQty').classList.contains('bad')"),'＋でも赤が消える')
        # 拡大の知らせ
        t(await pg.evaluate("typeof watchZoom")=='function','拡大の見張りがある')
        t(await pg.evaluate("!!window.visualViewport")==True,'visualViewport が使える')
        t(await pg.query_selector('#zoomBar')==None,'拡大していないときは出ない')
        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
