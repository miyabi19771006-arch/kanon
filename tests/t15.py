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

        # ① 出荷登録
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.click('#m-ship'); await pg.wait_for_timeout(300)
        await pg.click('#sCrop .chip'); await pg.wait_for_timeout(300)
        await pg.fill(f'[data-bsi="{sts[0]}"]','20'); await pg.wait_for_timeout(200)
        await pg.click('#sSave'); await pg.wait_for_timeout(600)
        t(await pg.evaluate("D.ship.length")==1,'① 出荷登録')

        # ② 販売登録
        await pg.click('#m-rec'); await pg.wait_for_timeout(500)
        await (await pg.query_selector('input[data-k="sold"]')).fill('6'); await pg.wait_for_timeout(300)
        await pg.click('#rcSave'); await pg.wait_for_timeout(500)
        t(await pg.evaluate("D.moves.length")==1,'② 販売登録')

        # トーストが保存ボタンに重なっていないこと
        g=await pg.evaluate("""()=>{const t=$('toast'),u=t.querySelector('.undo'),s=$('rcSave');
          const r=x=>x?x.getBoundingClientRect():null;const a=r(u),c=r(s);
          return {high:t.classList.contains('high'),
                  overlap:(a&&c)?!(a.bottom<=c.top||a.top>=c.bottom):null,
                  undoBottom:a?Math.round(a.bottom):null, saveTop:c?Math.round(c.top):null};}""")
        t(g['high']==True,'保存ボタンがあるので上に逃げる')
        t(g['overlap']==False,f"取り消すが保存ボタンに重ならない（取消下端{g['undoBottom']} / 保存上端{g['saveTop']}）")

        # ③ 出荷タブへ移ると取り消しは消える
        await pg.click('#m-ship'); await pg.wait_for_timeout(300)
        t(await pg.evaluate("$('toast').classList.contains('on')")==False,'③ 画面を移るとトーストが消える')
        t(await pg.evaluate("lastAdd.length")==0,'取り消しの対象も捨てる')

        # ④ 出荷をもう一度登録しても販売は消えない
        await pg.click('#sCrop .chip'); await pg.wait_for_timeout(300)
        await pg.fill(f'[data-bsi="{sts[1]}"]','10'); await pg.wait_for_timeout(200)
        await pg.click('#sSave'); await pg.wait_for_timeout(600)
        t(await pg.evaluate("D.moves.length")==1,'④ 出荷→販売→出荷でも販売が残る '+str(await pg.evaluate("D.moves.length")))
        t(await pg.evaluate("D.ship.length")==2,'出荷は2件')

        # ⑤ 保存ボタンの座標をタップしても取り消しにならない
        await pg.click('#m-rec'); await pg.wait_for_timeout(500)
        await (await pg.query_selector('input[data-k="sold"]')).fill('2'); await pg.wait_for_timeout(250)
        await pg.click('#rcSave'); await pg.wait_for_timeout(400)
        n=await pg.evaluate("D.moves.length")
        sb=await pg.evaluate("()=>{const r=$('rcSave').getBoundingClientRect();return [Math.round(r.left+r.width/2),Math.round(r.top+r.height/2)]}")
        await pg.mouse.click(sb[0],sb[1]); await pg.wait_for_timeout(600)
        t(await pg.evaluate("D.moves.length")>=n,'⑤ 保存ボタンを連打しても記録が消えない '+str(await pg.evaluate("D.moves.length")))

        # ⑥ 同じ画面にいれば取り消しは使える
        await pg.evaluate("()=>{D.ship=[];D.moves=[];save();refreshAll()}")
        await pg.click('#m-ship'); await pg.wait_for_timeout(300)
        await pg.click('#sCrop .chip'); await pg.wait_for_timeout(300)
        await pg.fill(f'[data-bsi="{sts[0]}"]','7'); await pg.wait_for_timeout(200)
        await pg.click('#sSave'); await pg.wait_for_timeout(500)
        t(await pg.evaluate("D.ship.length")==1,'⑥ 出荷を保存')
        await pg.click('#toast .undo'); await pg.wait_for_timeout(500)
        t(await pg.evaluate("D.ship.length")==0,'同じ画面なら取り消せる')
        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
