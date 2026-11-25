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

SETUP="""()=>{
  D.adv=true;D.plotOn=true;
  D.plots=[{id:'p1',crop:'小松菜',name:'1番',place:'ハウス',area:40,steps:[
    {id:'s1',n:'播種',date:addDays(today(),-20),t:'播種',m:60,done:false},
    {id:'s2',n:'防除1回目',date:addDays(today(),-3),t:'防除',m:45,done:false},
    {id:'s3',n:'収穫',date:today(),t:'収穫',m:90,done:false}
  ]}];
  D.work=[];D.harv=[];D.spray=[];D.fert=[];
  save();applyFeat();renderPlots();refreshAll();
}"""

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844})
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.on('console',lambda m:errs.append(m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(500)
        await pg.evaluate(SETUP); await pg.wait_for_timeout(300)

        # ---- 収穫の工程を完了 ----
        await pg.evaluate("goto('p-plan')"); await pg.wait_for_timeout(300)
        await pg.evaluate("openSheet(allTasks().find(x=>x.sid==='s3'))"); await pg.wait_for_timeout(300)
        await pg.fill('#shGot','120'); await pg.fill('#shNg','8')
        await pg.evaluate("finishTask(90)"); await pg.wait_for_timeout(400)
        st=await pg.evaluate("[D.work.length,D.harv.length,(D.plots[0].steps[2].rec||[]).length]")
        t(st==[1,1,2],'完了で作業1・収穫1、工程に記録が紐づく '+str(st))

        # ---- トーストの取り消し ----
        await pg.click('#toast .undo'); await pg.wait_for_timeout(400)
        st=await pg.evaluate("[D.work.length,D.harv.length,D.plots[0].steps[2].done]")
        t(st==[0,0,False],'取り消すと記録も完了も戻る '+str(st))

        # ---- もう一度完了（重複しないか）----
        await pg.evaluate("openSheet(allTasks().find(x=>x.sid==='s3'))"); await pg.wait_for_timeout(250)
        await pg.fill('#shGot','120')
        await pg.evaluate("finishTask(90)"); await pg.wait_for_timeout(400)
        st=await pg.evaluate("[D.work.length,D.harv.length]")
        t(st==[1,1],'やり直しても重複しない '+str(st))

        # ---- 予定タブからの未完了（確認ダイアログ）----
        await pg.evaluate("goto('p-plan')"); await pg.wait_for_timeout(300)
        await pg.evaluate("void undoTask(allTasks().find(x=>x.sid==='s3'))"); await pg.wait_for_timeout(350)
        t(await pg.is_visible('#sheetC'),'記録があると確認が出る')
        sub=await pg.inner_text('#cS')
        t('作業1件' in sub and '収穫1件' in sub,'消える記録の中身が出る: '+sub)
        await pg.click('#cOk'); await pg.wait_for_timeout(400)
        st=await pg.evaluate("[D.work.length,D.harv.length,D.plots[0].steps[2].done]")
        t(st==[0,0,False],'予定から未完了に戻すと記録も消える '+str(st))

        # ---- キャンセルしたら何も変わらない ----
        await pg.evaluate("openSheet(allTasks().find(x=>x.sid==='s3'))"); await pg.wait_for_timeout(250)
        await pg.fill('#shGot','50')
        await pg.evaluate("finishTask(60)"); await pg.wait_for_timeout(350)
        await pg.evaluate("void undoTask(allTasks().find(x=>x.sid==='s3'))"); await pg.wait_for_timeout(300)
        await pg.click('#cNo' if await pg.query_selector('#cNo') else '#cCancel'); await pg.wait_for_timeout(350)
        st=await pg.evaluate("[D.work.length,D.harv.length,D.plots[0].steps[2].done]")
        t(st==[1,1,True],'やめたら何も変わらない '+str(st))

        # ---- 作型タブの丸印から未完了に戻す ----
        await pg.evaluate("goto('p-plot')"); await pg.wait_for_timeout(350)
        await pg.click('[data-tog="p1"]'); await pg.wait_for_timeout(350)
        dots=await pg.query_selector_all('button.dot[data-unstep]')
        t(len(dots)==1,'完了した工程だけ丸が押せる '+str(len(dots)))
        if dots:
            bb=await dots[0].bounding_box()
            t(bb['height']>=8,'丸の大きさ '+str(round(bb['width'],1))+'x'+str(round(bb['height'],1)))
            await dots[0].click(); await pg.wait_for_timeout(350)
            t(await pg.is_visible('#sheetC'),'作型タブでも確認が出る')
            await pg.click('#cOk'); await pg.wait_for_timeout(400)
            st=await pg.evaluate("[D.work.length,D.harv.length,D.plots[0].steps[2].done]")
            t(st==[0,0,False],'作型タブから未完了に戻せる '+str(st))
            left=await pg.query_selector_all('button.dot[data-unstep]')
            t(len(left)==0,'戻すと丸が押せなくなる')

        # ---- 記録ゼロの工程（時間0で完了）----
        await pg.evaluate("openSheet(allTasks().find(x=>x.sid==='s1'))"); await pg.wait_for_timeout(250)
        await pg.evaluate("finishTask(0)"); await pg.wait_for_timeout(350)
        t(await pg.evaluate("D.plots[0].steps[0].done")==True,'時間0でも完了できる')
        await pg.evaluate("goto('p-plot')"); await pg.wait_for_timeout(300)
        await pg.click('[data-tog="p1"]'); await pg.wait_for_timeout(300)
        d2=await pg.query_selector_all('button.dot[data-unstep]')
        await d2[0].click(); await pg.wait_for_timeout(300)
        await pg.click('#cOk'); await pg.wait_for_timeout(350)
        t(await pg.evaluate("D.plots[0].steps[0].done")==False,'記録なしの工程も戻せる')

        await pg.evaluate("goto('p-plot')"); await pg.wait_for_timeout(200)
        await pg.click('[data-tog="p1"]'); await pg.wait_for_timeout(300)
        await pg.screenshot(path=os.path.join(OUT,'plot3.png'),full_page=True)
        await b.close()
asyncio.run(main())
print('\n'.join('OK '+x for x in ok))
print('\n'.join('NG '+x for x in ng))
print('JSエラー:',len(errs),errs[:6] if errs else '')
