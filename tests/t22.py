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
        await pg.goto(APPURL); await pg.wait_for_timeout(800)
        body=await pg.inner_text('body')
        t('話して入力' not in body,'話して入力が消えている')
        t('キーボードのマイク' not in await pg.content(),'マイクの案内も消えている')
        for i in ['sayText','sayGo','sayHelp','fldSay','sayNote']:
            t(await pg.query_selector('#'+i) is None, i+' が残っていない')
        # 出荷の入力がいままでどおり動く
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(300)
        y=await pg.evaluate("""()=>$('sCrop').getBoundingClientRect().top""")
        t(y<520,'品目が画面の上のほうに来た top='+str(round(y)))
        await pg.evaluate("()=>{sel.crop='ベビーリーフ';renderForms()}"); await pg.wait_for_timeout(300)
        await pg.evaluate("()=>{setShipQty(D.stores[0],12);setShipQty(D.stores[1],8);renderShipRows()}")
        await pg.wait_for_timeout(200)
        await pg.evaluate("()=>$('sSave').click()"); await pg.wait_for_timeout(600)
        n=await pg.evaluate("()=>D.ship.length")
        t(n==2,'出荷は2件そのまま記録できる n='+str(n))
        await pg.screenshot(path=os.path.join(OUT,'ship_nosay.png'),full_page=True)
        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
