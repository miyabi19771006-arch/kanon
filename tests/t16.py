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
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(700)
        sts=await pg.evaluate("D.stores")

        # 出荷を登録
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.click('#m-ship'); await pg.wait_for_timeout(300)
        await pg.click('#sCrop .chip'); await pg.wait_for_timeout(300)
        await pg.fill(f'[data-bsi="{sts[0]}"]','12'); await pg.wait_for_timeout(200)
        await pg.click('#sSave'); await pg.wait_for_timeout(700)
        t('済 12点' in await pg.inner_text('#sRows'),'保存すると「済 12点」が出る')
        t('記録済み' in await pg.inner_text('#sHint'),'案内も出る')

        # 一覧から削除
        sid=await pg.evaluate("D.ship[0].id")
        await pg.evaluate(f"openEdit('ship','{sid}')"); await pg.wait_for_timeout(400)
        await pg.click('#eDel'); await pg.wait_for_timeout(400)
        if await pg.is_visible('#sheetC'): await pg.click('#cOk'); await pg.wait_for_timeout(600)
        t(await pg.evaluate("D.ship.length")==0,'記録が消えた')

        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.click('#m-ship'); await pg.wait_for_timeout(400)
        rows=await pg.inner_text('#sRows'); hint=await pg.inner_text('#sHint')
        t('済' not in rows,'★「済」が消えている')
        t('記録済み' not in hint,'★ 案内も消えている: '+repr(hint[:30]))

        # 一覧から数量を直したとき
        await pg.fill(f'[data-bsi="{sts[0]}"]','20'); await pg.wait_for_timeout(200)
        await pg.click('#sSave'); await pg.wait_for_timeout(700)
        sid=await pg.evaluate("D.ship[0].id")
        await pg.evaluate(f"openEdit('ship','{sid}')"); await pg.wait_for_timeout(400)
        await pg.fill('#eQty','8'); await pg.click('#eOk'); await pg.wait_for_timeout(600)
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.click('#m-ship'); await pg.wait_for_timeout(400)
        t('済 8点' in await pg.inner_text('#sRows'),'直した数が反映される '+str('済 8点' in await pg.inner_text('#sRows')))

        # 入力中は触らない
        await pg.fill(f'[data-bsi="{sts[1]}"]','5')
        await pg.focus(f'[data-bsi="{sts[1]}"]')
        await pg.evaluate("refreshAll()"); await pg.wait_for_timeout(300)
        t(await pg.input_value(f'[data-bsi="{sts[1]}"]')=='5','入力中の値は消えない')
        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
