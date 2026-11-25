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
errs=[];ok=[];ng=[]
def t(c,m):(ok if c else ng).append(m)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844})
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append('PAGE '+str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(500)
        # 一通りデータを作る
        await pg.evaluate("""()=>{
          const d=today();
          D.ship.push({id:'s1',date:d,crop:'ベビーリーフ',store:D.stores[0],qty:50,price:200});
          D.moves.push({id:'m1',date:d,type:'sold',crop:'ベビーリーフ',store:D.stores[0],qty:20,price:200});
          D.work.push({id:'w1',date:d,crop:'小松菜',task:'収穫',min:60,ppl:1});
          D.spray.push({id:'sp1',date:d,crop:'小松菜',chem:'ダコニール',dil:'1000',target:'べと病',tank:100,dose:'100',unit:'mL'});
          D.fert.push({id:'f1',date:d,crop:'小松菜',name:'液肥A',dil:'500'});
          D.harv.push({id:'h1',date:d,crop:'小松菜',got:100,ng:5,ok:95});
          D.exp.push({id:'e1',date:d,cat:'資材費',note:'袋',amt:1200});
          D.plots.push({id:'p1',crop:'小松菜',name:'1番',place:'ハウス',area:40,steps:[
            {id:'x1',n:'播種',date:addDays(d,-20),t:'播種',m:60,done:true,did:addDays(d,-19)},
            {id:'x2',n:'収穫',date:d,t:'収穫',m:90,done:false}]});
          save();
        }"""); await pg.reload(); await pg.wait_for_timeout(600)
        for pid,name in [('p-plan','予定'),('p-rec','記録'),('p-plot','作型'),('p-list','一覧'),('p-sum','集計'),('p-set','設定')]:
            await pg.evaluate(f"goto('{pid}')"); await pg.wait_for_timeout(450)
            vis=await pg.is_visible(f'#{pid}')
            t(vis,name+'タブが開く')
            await pg.screenshot(path=os.path.join(OUT,'sm_'+pid+'.png'),full_page=True)
        # ガント
        await pg.evaluate("goto('p-plot')"); await pg.wait_for_timeout(300)
        bt=await pg.query_selector('[data-pv="gantt"]') or await pg.query_selector('#plotView [data-v="gantt"]')
        if bt:
            await bt.click(); await pg.wait_for_timeout(500); t(True,'ガント表示')
        # 集計の数字
        await pg.evaluate("goto('p-sum')"); await pg.wait_for_timeout(400)
        txt=await pg.inner_text('#p-sum')
        t('4,000' in txt or '4000' in txt, '売上が出ている')
        await b.close()
asyncio.run(main())
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
print('JSエラー:',len(errs)); [print(' ',e) for e in errs[:8]]
