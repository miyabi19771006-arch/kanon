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
        ctx=await b.new_context(viewport={'width':390,'height':844})
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append('PAGE '+str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(600)
        await pg.evaluate("()=>{D.adv=true;D.plotOn=true;save();applyFeat()}"); await pg.wait_for_timeout(200)

        # 初期登録
        rt=await pg.evaluate("D.routines")
        t(len(rt)==1 and rt[0]['crop']=='ベビーリーフ','ベビーリーフの収穫が最初から入る '+str(rt))

        # 期間・曜日の判定
        chk=await pg.evaluate("""()=>{
          const r=D.routines[0];
          return {
            金11月:rtOn(r,'2026-11-20'), 日11月:rtOn(r,'2026-11-22'),
            月7月:rtOn(r,'2026-07-06'), 月6月:rtOn(r,'2026-06-29'),
            月10月:rtOn(r,'2026-10-05'), 月1月:rtOn(r,'2027-01-04')
          };
        }""")
        t(chk['金11月'] and not chk['日11月'],'曜日で出し分ける '+str(chk))
        t(not chk['月7月'] and chk['月6月'] and chk['月10月'] and chk['月1月'],'年をまたぐ期間が効く '+str(chk))

        # 予定タブに出る（月〜金のときだけ）
        await pg.evaluate("goto('p-plan')"); await pg.wait_for_timeout(400)
        body=await pg.inner_text('#planBody')
        dow=await pg.evaluate("new Date().getDay()")
        shown='ベビーリーフ' in body
        t(shown==(1<=dow<=5),f'今日は{"日月火水木金土"[dow]}曜。予定に出る={shown}')

        # 強制的に今日を対象にする
        await pg.evaluate("()=>{D.routines[0].dows=[0,1,2,3,4,5,6];save();renderPlan()}")
        await pg.wait_for_timeout(350)
        n=await pg.evaluate("allTasks().filter(x=>x.kind==='rt').length")
        t(n==1,'毎日にすると必ず出る')
        t('ベビーリーフ' in await pg.inner_text('#planBody'),'予定タブに名前が出る')
        # 先の予定には出さない
        far=await pg.evaluate("allTasks().filter(x=>x.kind==='rt'&&x.date!==today()).length")
        t(far==0,'今日のぶんだけで、先には出さない')

        # 完了 → 作業と収穫が入る
        rid=await pg.evaluate("D.routines[0].id")
        await pg.evaluate(f"openSheet(allTasks().find(x=>x.kind==='rt'))"); await pg.wait_for_timeout(350)
        t(await pg.is_visible('#sheet'),'完了シートが開く')
        await pg.fill('#shGot','240'); await pg.fill('#shNg','12')
        await pg.evaluate("finishTask(120)"); await pg.wait_for_timeout(450)
        st=await pg.evaluate("[D.work.length,D.harv.length,Object.keys(D.rlog).length]")
        t(st==[1,1,1],'完了で作業・収穫・記録が残る '+str(st))
        t(await pg.evaluate("allTasks().find(x=>x.kind==='rt').done")==True,'予定に✓が付く')

        # 取り消し
        await pg.click('#toast .undo'); await pg.wait_for_timeout(400)
        st=await pg.evaluate("[D.work.length,D.harv.length,Object.keys(D.rlog).length]")
        t(st==[0,0,0],'取り消すと全部戻る '+str(st))

        # もう一度完了 → 予定から未完了に戻す
        await pg.evaluate("openSheet(allTasks().find(x=>x.kind==='rt'))"); await pg.wait_for_timeout(300)
        await pg.fill('#shGot','200')
        await pg.evaluate("finishTask(120)"); await pg.wait_for_timeout(400)
        await pg.evaluate("void undoTask(allTasks().find(x=>x.kind==='rt'))"); await pg.wait_for_timeout(350)
        t(await pg.is_visible('#sheetC'),'確認が出る')
        await pg.click('#cOk'); await pg.wait_for_timeout(400)
        st=await pg.evaluate("[D.work.length,D.harv.length,Object.keys(D.rlog).length]")
        t(st==[0,0,0],'未完了に戻すと記録も消える '+str(st))

        # 記録タブから入れても勝手に済みにはしない（時給が狂うため）
        await pg.evaluate("""()=>{D.work.push({id:'zz',date:today(),crop:'ベビーリーフ',task:'収穫',min:60,ppl:1});save();renderPlan()}""")
        await pg.wait_for_timeout(300)
        rt2=await pg.evaluate("allTasks().find(x=>x.kind==='rt')")
        t(rt2['done']==False,'記録タブの入力では済みにしない')
        t(rt2['prog']=='記録済み？','ただし注意書きは出る: '+str(rt2['prog']))
        t(await pg.evaluate("D.work.length")==1,'記録は残る')
        await pg.evaluate("()=>{D.work=[];save();renderPlan()}")

        # 設定から登録
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(400)
        await pg.evaluate("()=>{D.routines[0].dows=[1,2,3,4,5];save();renderRt()}")
        await pg.wait_for_timeout(250)
        t((await pg.inner_text('#rtList')).count('月〜金')==1,'設定に一覧が出る: '+(await pg.inner_text('#rtList')).replace(chr(10),' / '))
        await pg.click('#rtAdd'); await pg.wait_for_timeout(350)
        t(await pg.is_visible('#sheetRt'),'追加シートが開く')
        await pg.select_option('#rtCrop','小松菜')
        await pg.select_option('#rtTask','配達')
        await pg.click('#rtEveryday'); await pg.wait_for_timeout(200)
        await pg.click('#rtAllYear'); await pg.wait_for_timeout(250)
        t(not await pg.is_visible('#rtRange'),'一年じゅうにすると期間が隠れる')
        await pg.click('#rtOk'); await pg.wait_for_timeout(400)
        rts=await pg.evaluate("D.routines.map(r=>[r.crop,r.task,r.dows.length,r.from])")
        t(len(rts)==2 and rts[1]==['小松菜','配達',7,None],'登録できる '+str(rts))

        # 曜日なしは弾く
        await pg.click('#rtAdd'); await pg.wait_for_timeout(300)
        for i in range(7):
            btn=(await pg.query_selector_all('#rtDow .chip'))[i]
            if await btn.get_attribute('aria-pressed')=='true': await btn.click()
        await pg.wait_for_timeout(200)
        await pg.click('#rtOk'); await pg.wait_for_timeout(300)
        t('曜日' in await pg.inner_text('#errRt'),'曜日なしは弾く: '+(await pg.inner_text('#errRt')))
        await pg.click('#rtCancel'); await pg.wait_for_timeout(250)
        t(await pg.evaluate("D.routines.length")==2,'やめたら増えない')

        # 編集
        await pg.click(f'[data-rtedit="{rid}"]'); await pg.wait_for_timeout(350)
        await pg.fill('#rtMin','90'); await pg.click('#rtOk'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("D.routines.length")==2 and await pg.evaluate("D.routines[0].min")==90,'直せる（増えない）')

        # 削除
        await pg.click(f'[data-rtdel="{rid}"]'); await pg.wait_for_timeout(300)
        await pg.click('#cOk'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("D.routines.length")==1,'消せる')

        # バックアップにも乗る
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=os.path.join(OUT,'rt_set.png'),full_page=True)
        await pg.evaluate("()=>{D.routines[0].dows=[0,1,2,3,4,5,6];save();renderPlan()}")
        await pg.evaluate("goto('p-plan')"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=os.path.join(OUT,'rt_plan.png'),full_page=True)
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
print('JSエラー:',len(errs)); [print(' ',e) for e in errs[:6]]
