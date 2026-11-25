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
SEED="""()=>{const d=today();
  D.ship.push({id:'s0',date:d,crop:'小松菜',store:D.stores[0],qty:10,price:100});
  D.moves.push({id:'v0',date:d,type:'sold',crop:'小松菜',store:D.stores[0],qty:4,price:100});
  D.exp.push({id:'e0',date:d,cat:'種苗費',amt:1200,note:'種'});
  D.work.push({id:'w0',date:d,crop:'小松菜',task:'収穫',min:60,ppl:1});
  D.harv.push({id:'h0',date:d,crop:'小松菜',got:12,ok:10,ng:2});
  D.spray.push({id:'p0',date:d,crop:'小松菜',chem:'アファーム',dil:1000,dose:'100L',target:'アブラムシ'});
  D.fert=D.fert||[];D.fert.push({id:'f0',date:d,crop:'小松菜',name:'液肥A',dil:500});
  save();refreshAll()}"""
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,color_scheme='dark')
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(800)
        await pg.evaluate(SEED); await pg.wait_for_timeout(200)

        # ① オフのとき 一覧の種類は3つだけ
        await pg.evaluate("goto('p-list')"); await pg.wait_for_timeout(400)
        seg=await pg.evaluate("""()=>[...document.querySelectorAll('#lSeg button')].filter(b=>b.getClientRects().length>0).map(b=>b.textContent)""")
        t(seg==['出荷','販売・回収','経費'],'一覧の種類は3つ '+str(seg))

        # ② 隠した記録の件数を知らせる
        body=await pg.inner_text('#lBody')
        t('4件' in body and '隠しています' in body,'隠した4件を知らせる')

        # ③ 隠した種類を開いていたら出荷に戻す
        await pg.evaluate("()=>{lKind='work';renderList()}"); await pg.wait_for_timeout(300)
        t(await pg.evaluate("lKind")=='ship','作業を開いていたら出荷に戻る')
        pr=await pg.evaluate("""()=>$('lSeg').querySelector('[data-k=ship]').getAttribute('aria-pressed')""")
        t(pr=='true','出荷ボタンが押された形になる')

        # ④ カレンダーの凡例と点
        await pg.evaluate("()=>setListView('cal')"); await pg.wait_for_timeout(400)
        lg=await pg.evaluate("""()=>[...document.querySelectorAll('#calWrap .callegend span')].filter(s=>s.getClientRects().length>0).map(s=>s.textContent.trim())""")
        t(all(x not in lg for x in ['作業','防除','収穫','液肥']),'凡例に作業・防除・収穫・液肥が出ない '+str(lg))
        dots=await pg.evaluate("""()=>{const c=document.querySelector('[data-cal="'+today()+'"]');
          return [...c.querySelectorAll('.cdot')].map(d=>[...d.classList].find(x=>x.startsWith('t-')))}""")
        t(sorted(dots)==['t-exp','t-ship','t-sold'],'今日の点は出荷・販売・経費だけ '+str(dots))
        await pg.evaluate("()=>{calSel=today();renderCalDay()}"); await pg.wait_for_timeout(300)
        cd=await pg.inner_text('#calDay')
        t(all(x not in cd for x in ['作業','防除','液肥']),'その日の明細にも作業系が出ない')
        t('出荷' in cd and '経費' in cd,'出荷と経費は出ている')
        await pg.screenshot(path=os.path.join(OUT,'list_cal_off.png'),full_page=True)

        # ⑤ オンにすると戻る
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(300)
        await pg.click('#advTog'); await pg.wait_for_timeout(500)
        await pg.evaluate("goto('p-list')"); await pg.evaluate("()=>setListView('list')"); await pg.wait_for_timeout(400)
        seg2=await pg.evaluate("""()=>[...document.querySelectorAll('#lSeg button')].filter(b=>b.getClientRects().length>0).map(b=>b.textContent)""")
        t(len(seg2)==7,'オンで7種類に戻る '+str(seg2))
        t('隠しています' not in await pg.inner_text('#lBody'),'オンならお知らせは消える')
        await pg.evaluate("()=>setListView('cal')"); await pg.wait_for_timeout(400)
        dots2=await pg.evaluate("""()=>{const c=document.querySelector('[data-cal="'+today()+'"]');
          return [...c.querySelectorAll('.cdot')].map(d=>[...d.classList].find(x=>x.startsWith('t-')))}""")
        t(len(dots2)==7,'点も7つに戻る '+str(dots2))

        # ⑥ 記録そのものは消えていない
        n=await pg.evaluate("()=>D.work.length+D.harv.length+D.spray.length+D.fert.length")
        t(n==4,'記録は4件のまま')
        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
