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

        # ① まっさらな端末 → お金まわりだけ
        await pg.goto(APPURL); await pg.wait_for_timeout(800)
        t(await pg.evaluate("D.adv")==False,'新しい端末は作業オフ')
        t(await pg.evaluate("D.plotOn")==False,'新しい端末は作型オフ')
        nav=await pg.evaluate("""()=>[...document.querySelectorAll('nav button')].filter(b=>b.offsetParent!==null).map(b=>b.querySelector('b').textContent)""")
        t(nav==['記録','一覧','集計'],'タブは3つ '+str(nav))
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(300)
        md=await pg.evaluate("""()=>[...document.querySelectorAll('#p-rec .modes button')].filter(b=>b.offsetParent!==null).map(b=>b.textContent)""")
        t(md==['出荷','販売','直販','経費'],'帯は4つ '+str(md))
        t(await pg.evaluate("$('m-ship').getAttribute('aria-pressed')")=='true','出荷で開く')
        await pg.evaluate("""()=>{D.ship.push({id:'s0',date:today(),crop:'小松菜',store:D.stores[0],qty:10,price:100});
          D.moves.push({id:'v0',date:today(),type:'sold',crop:'小松菜',store:D.stores[0],qty:10,price:100});
          D.work.push({id:'w0',date:today(),crop:'小松菜',task:'収穫',min:60,ppl:1});
          uFrom='';uTo='';save();refreshAll();renderSum()}""")
        await pg.evaluate("goto('p-sum')"); await pg.wait_for_timeout(500)
        sm=await pg.inner_text('#uBody')
        t('時給' not in sm,'集計に時給が出ない（データはあるのに）')
        t('規格外' not in sm,'規格外も出ない')
        t('売上' in sm,'売上は出ている')
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(400)
        t('作業の種類' not in await pg.inner_text('#p-set'),'設定の作業の種類も隠れる')
        t('毎日の作業' not in await pg.inner_text('#p-set'),'毎日の作業も隠れる')
        await pg.screenshot(path=os.path.join(OUT,'feat_off.png'),full_page=True)

        # ② オンにすると戻る
        await pg.click('#advTog'); await pg.wait_for_timeout(400)
        await pg.click('#plotTog'); await pg.wait_for_timeout(400)
        nav=await pg.evaluate("""()=>[...document.querySelectorAll('nav button')].filter(b=>b.offsetParent!==null).map(b=>b.querySelector('b').textContent)""")
        t(nav==['予定','記録','作型','一覧','集計'],'タブが5つに戻る '+str(nav))
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(300)
        md=await pg.evaluate("""()=>[...document.querySelectorAll('#p-rec .modes button')].filter(b=>b.offsetParent!==null).map(b=>b.textContent)""")
        t(md[0]=='作業','作業が戻る '+str(md))
        await pg.evaluate("""()=>{D.work.push({id:'w0',date:today(),crop:'小松菜',task:'収穫',min:60,ppl:1});
          D.ship.push({id:'s0',date:today(),crop:'小松菜',store:D.stores[0],qty:10,price:100});
          D.moves.push({id:'v0',date:today(),type:'sold',crop:'小松菜',store:D.stores[0],qty:10,price:100});
          uFrom='';uTo='';save();refreshAll();renderSum()}""")
        await pg.evaluate("goto('p-sum')"); await pg.wait_for_timeout(500)
        sm2=await pg.inner_text('#uBody')
        t('時給' in sm2,'時給も戻る')
        t('規格外' in sm2,'規格外の列も戻る')

        # ③ 設定は残る（開き直しても）
        await pg.reload(); await pg.wait_for_timeout(800)
        t(await pg.evaluate("D.adv")==True and await pg.evaluate("D.plotOn")==True,'設定が残る')

        # ④ 記録は消えない
        n0=await pg.evaluate("D.work.length")
        await pg.evaluate("()=>{D.adv=false;save();applyFeat();renderSum()}"); await pg.wait_for_timeout(400)
        t(await pg.evaluate("D.work.length")==n0,'オフにしても記録は残る')
        await pg.evaluate("()=>{D.adv=true;save();applyFeat();renderSum()}"); await pg.wait_for_timeout(400)
        t(await pg.evaluate("D.work.length")==n0,'オンに戻すと出てくる')

        # ⑤ 既存の端末（seed=4）は全部出たまま
        await pg.evaluate("""()=>{const d=JSON.parse(localStorage.getItem('nokiroku:v2'));
          delete d.adv;delete d.plotOn;d.seed=4;localStorage.setItem('nokiroku:v2',JSON.stringify(d))}""")
        await pg.reload(); await pg.wait_for_timeout(800)
        t(await pg.evaluate("D.adv")==True and await pg.evaluate("D.plotOn")==True,'いま使っている端末は変わらない')
        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
