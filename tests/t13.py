# -*- coding: utf-8 -*-
import asyncio,os
from playwright.async_api import async_playwright
import os, pathlib
# このテストが見にいく kanon 本体。既定はリポジトリの index.html。
# 別のファイルを試すときは KANON=/path/to/app.html python3 tests/t5.py
ROOT = pathlib.Path(__file__).resolve().parent.parent
APP  = os.environ.get("KANON", str(ROOT / "index.html"))
APPURL = "file://" + APP
OUTDIR = os.environ.get("KANON_OUT", str(ROOT / "tests" / "_shots"))
os.makedirs(OUTDIR, exist_ok=True)

OUT=OUTDIR
ok=[];ng=[];errs=[]
def t(c,m):(ok if c else ng).append(m)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,color_scheme='dark')
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(700)
        sts=await pg.evaluate("D.stores")

        async def openShip():
            await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
            await pg.click('#m-ship'); await pg.wait_for_timeout(300)

        # --- 1. 同じ品目を押し直しても消えない ---
        await openShip()
        await pg.click('#sCrop .chip'); await pg.wait_for_timeout(300)
        for s_ in sts[:5]: await pg.fill(f'[data-bsi="{s_}"]','10')
        await pg.wait_for_timeout(250)
        t(await pg.evaluate("Object.keys(shipQty).length")==5,'5店入力')
        await pg.click('#sCrop .chip'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("Object.keys(shipQty).length")==5,'同じ品目を押し直しても消えない')
        t(not await pg.is_visible('#sheetC'),'余計な確認も出ない')

        # --- 2. 品目を変えるときは確認する ---
        chips=await pg.query_selector_all('#sCrop .chip')
        await chips[1].click(); await pg.wait_for_timeout(400)
        t(await pg.is_visible('#sheetC'),'品目を変えると確認が出る')
        t('まだ保存されていません' in await pg.inner_text('#cS'),'消えることを伝える')
        await pg.click('#cNo'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("Object.keys(shipQty).length")==5,'やめたら入力は残る')
        t(await pg.evaluate("sel.crop")==await pg.evaluate("shipCrop"),'品目も元に戻る')

        # --- 3. 1回目の保存 ---
        await pg.click('#sSave'); await pg.wait_for_timeout(600)
        t(await pg.evaluate("D.ship.length")==5,'1回目は確認なしで保存 '+str(await pg.evaluate("D.ship.length")))
        t(not await pg.is_visible('#sheetC'),'1回目に確認は出ない')

        # --- 4. 別の店を足すだけなら確認なし ---
        await pg.click('#sCrop .chip'); await pg.wait_for_timeout(350)
        hint=await pg.inner_text('#sHint')
        t('記録済み' in hint,'済んだ分を知らせる: '+hint.replace(chr(10),' ')[:46])
        rows=await pg.inner_text('#sRows')
        t('済 10点' in rows,'行にも「済」が出る')
        await pg.fill(f'[data-bsi="{sts[5]}"]','8'); await pg.wait_for_timeout(250)
        await pg.click('#sSave'); await pg.wait_for_timeout(600)
        t(not await pg.is_visible('#sheetC'),'まだの店に出すだけなら確認は出ない')
        t(await pg.evaluate("D.ship.length")==6,'そのまま保存される '+str(await pg.evaluate("D.ship.length")))

        # --- 5. 同じ店に重ねるときだけ確認 ---
        await pg.click('#sCrop .chip'); await pg.wait_for_timeout(300)
        await pg.fill(f'[data-bsi="{sts[0]}"]','5'); await pg.wait_for_timeout(250)
        await pg.click('#sSave'); await pg.wait_for_timeout(500)
        t(await pg.is_visible('#sheetC'),'同じ店に重ねると確認が出る')
        sub=await pg.inner_text('#cS')
        t('すでに記録しています' in sub and '足すと合計15点' in sub,'何点になるか出す: '+sub.replace(chr(10),' ')[:60])
        t(await pg.inner_text('#cOk')=='足す','ボタンは「足す」')
        await pg.click('#cOk'); await pg.wait_for_timeout(500)
        t(await pg.evaluate("D.ship.length")==7,'足せる')

        # --- 6. 未入力で保存したときの知らせ ---
        await pg.evaluate("()=>{shipQty={};renderShipRows()}")
        await pg.evaluate("window.scrollTo(0,document.body.scrollHeight)"); await pg.wait_for_timeout(300)
        await pg.click('#sSave'); await pg.wait_for_timeout(300)
        t(await pg.evaluate("$('toast').classList.contains('on')"),'トーストが出る')
        await pg.wait_for_timeout(2500)
        t(await pg.evaluate("$('toast').classList.contains('on')"),'2.8秒たっても消えない（以前は1.6秒）')

        # --- 7. 入力欄の文字が16px以上か（実測）---
        await pg.evaluate("goto('p-plot')"); await pg.wait_for_timeout(400)
        small=await pg.evaluate("""()=>{
          const out=[];
          document.querySelectorAll('input,select,textarea').forEach(el=>{
            const px=parseFloat(getComputedStyle(el).fontSize);
            if(px<16)out.push((el.id||el.className||el.type)+' '+px+'px');
          });
          return out;}""")
        t(len(small)==0,'16px未満の入力欄なし '+str(small[:4]))
        for pid in ['p-rec','p-list','p-sum','p-set','p-plan']:
            await pg.evaluate(f"goto('{pid}')"); await pg.wait_for_timeout(300)
            sm=await pg.evaluate("""()=>{const o=[];document.querySelectorAll('input,select,textarea').forEach(el=>{
              const px=parseFloat(getComputedStyle(el).fontSize);if(px<16)o.push((el.id||el.className)+' '+px)});return o}""")
            t(len(sm)==0, pid+' も16px以上 '+str(sm[:3]))
        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
