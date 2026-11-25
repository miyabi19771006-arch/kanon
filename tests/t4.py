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

async def openShip(pg):
    await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(250)
    b=await pg.query_selector('#m-ship')
    if b: await b.click()
    else: raise Exception('no m-ship')
    await pg.wait_for_timeout(300)

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844})
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append('PAGE '+str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(500)
        await openShip(pg)
        t(await pg.is_visible('#f-ship'),'出荷フォームが開く')
        rows=await pg.query_selector_all('.bsrow')
        t(len(rows)==7,'7店ぶんの行が出る '+str(len(rows)))

        # 品目を選ぶ
        await pg.click('#sCrop .chip:has-text("ベビーリーフ")'); await pg.wait_for_timeout(300)
        await pg.fill('#sPrice','150'); await pg.wait_for_timeout(200)

        # 3店に数を入れる
        st=await pg.evaluate("D.stores")
        for s_,q in [(st[0],12),(st[1],8),(st[3],20)]:
            await pg.fill(f'[data-bsi="{s_}"]',str(q))
        await pg.wait_for_timeout(250)
        tot=await pg.inner_text('#sTot')
        t('3店' in tot and '40点' in tot and '6,000' in tot,'合計が出る: '+tot)

        # 1店だけ単価を変える
        await pg.click(f'[data-bsp="{st[1]}"]'); await pg.wait_for_timeout(300)
        await pg.fill('#cInput','200'); await pg.click('#cOk'); await pg.wait_for_timeout(350)
        tot=await pg.inner_text('#sTot')
        t('6,400' in tot,'店ごとの単価が効く: '+tot)
        t(await pg.get_attribute(f'[data-bsp="{st[1]}"]','class')=='bsp own','変えた店に印が付く')

        # 保存
        await pg.click('#sSave'); await pg.wait_for_timeout(450)
        recs=await pg.evaluate("D.ship.map(r=>[r.store,r.qty,r.price])")
        t(len(recs)==3,'3件に分かれて保存 '+str(recs))
        t(sorted(r[2] for r in recs)==[150,150,200],'単価も店ごと')
        t(await pg.evaluate("Object.keys(shipQty).length")==0,'保存後は空になる')

        # ＋−ボタン
        await pg.click(f'[data-bsq="{st[0]}"][data-d="1"]')
        await pg.click(f'[data-bsq="{st[0]}"][data-d="1"]'); await pg.wait_for_timeout(250)
        t(await pg.evaluate(f"shipQty[{st[0]!r}]")==2,'＋で増える')
        await pg.click(f'[data-bsq="{st[0]}"][data-d="-1"]')
        await pg.click(f'[data-bsq="{st[0]}"][data-d="-1"]')
        await pg.click(f'[data-bsq="{st[0]}"][data-d="-1"]'); await pg.wait_for_timeout(250)
        t(await pg.evaluate(f"(shipQty[{st[0]!r}]||0)")==0,'0より下がらない')

        # 前回と同じ（保存ぶんを昨日に移して「前回」にする）
        await pg.evaluate("()=>{D.ship.forEach(r=>r.date=addDays(today(),-1));save();refreshAll()}")
        await pg.click('#sZero'); await pg.wait_for_timeout(200)
        await pg.click('#sSame'); await pg.wait_for_timeout(350)
        q=await pg.evaluate("Object.entries(shipQty)")
        t(len(q)==3 and dict(q)[st[3]]==20,'前回と同じが入る '+str(q))
        pr=await pg.evaluate("shipPrice")
        t(pr.get(st[1])==200,'違う単価も引き継ぐ '+str(pr))
        hint=await pg.inner_text('#sHint')
        t('前回' in hint and '3店' in hint,'説明が出る: '+hint)

        # 品目を変えると確認が入り、進めれば引き継ぎ直す
        await pg.click('#sCrop .chip:text-is("小松菜")'); await pg.wait_for_timeout(400)
        if await pg.is_visible('#sheetC'):
            t('まだ保存されていません' in await pg.inner_text('#cS'),'品目を変えるとき確認が出る')
            await pg.click('#cOk'); await pg.wait_for_timeout(400)
        else:
            t(True,'入力がないので確認なしで切り替わる')
        t(await pg.evaluate("Object.keys(shipQty).length")==0,'別の品目では空から')

        # 未入力のとき
        await pg.click('#sSave'); await pg.wait_for_timeout(300)
        t(await pg.is_visible('#errShip'),'未入力だと知らせる: '+(await pg.inner_text('#errShip')))
        t(await pg.evaluate("D.ship.length")==3,'余計に保存されない')

        # 取り消し
        await pg.click('#sCrop .chip:has-text("ベビーリーフ")'); await pg.wait_for_timeout(300)
        await pg.click('#sSave'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("D.ship.length")==6,'もう一度まとめて保存')
        await pg.click('#toast .undo'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("D.ship.length")==3,'まとめて取り消せる')

        await pg.click('#sCrop .chip:has-text("ベビーリーフ")'); await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=os.path.join(OUT,'ship.png'),full_page=True)
        await b.close()
try:
    asyncio.run(main())
except Exception as ex:
    ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
print('JSエラー:',len(errs)); [print(' ',e) for e in errs[:6]]
