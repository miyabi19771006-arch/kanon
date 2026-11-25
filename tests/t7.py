# -*- coding: utf-8 -*-
import asyncio,os,json
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
        ctx=await b.new_context(viewport={'width':390,'height':844},accept_downloads=True)
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append('PAGE '+str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(600)
        A=lambda: pg.evaluate("D.stores[0]")
        st=await A()

        # ---- 1. 過去日にさかのぼっての二重計上 ----
        await pg.evaluate(f"""()=>{{
          D.ship=[{{id:'s1',date:'2026-11-01',crop:'小松菜',store:{st!r},qty:10,price:100}}];
          D.moves=[{{id:'m1',date:'2026-11-20',type:'sold',crop:'小松菜',store:{st!r},qty:10,price:100}}];
          save();refreshAll();}}""")
        v=await pg.evaluate(f"stockOf({st!r},'小松菜','2026-11-10')")
        t(v['q']==0 and v['asOf']==10 and v['total']==0,'遡ってもあとで売れた分を引く '+str(v))
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.click('#m-rec'); await pg.wait_for_timeout(250)
        await pg.fill('#rcDate','2026-11-10'); await pg.dispatch_event('#rcDate','change')
        await pg.wait_for_timeout(400)
        t((await pg.query_selector_all('.sh-card'))==[] or await pg.evaluate("D.moves.length")==1,'過去日でカードが出ない')
        body=await pg.inner_text('#rcBody')
        t('在庫がありません' in body,'売れる数0なので出さない')

        # ---- 2. 棚残マイナスの可視化 ----
        await pg.evaluate(f"""()=>{{
          D.ship=[{{id:'s1',date:'2026-11-01',crop:'小松菜',store:{st!r},qty:10,price:100}}];
          D.moves=[{{id:'m1',date:'2026-11-05',type:'sold',crop:'小松菜',store:{st!r},qty:25,price:100}}];
          save();refreshAll();}}""")
        a=await pg.evaluate("auditShelf()")
        t(len(a)==1 and a[0]['over']==15,'つじつまの不足を数える '+str(a))
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(400)
        t('合わない組み合わせが1件' in await pg.inner_text('#auditBox'),'設定の点検に出る')
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.click('#m-rec'); await pg.wait_for_timeout(350)
        t('つじつまの合わない記録' in await pg.inner_text('#rcBody'),'販売画面にも赤帯が出る')

        # ---- 3. 一覧からの編集ガード ----
        await pg.evaluate(f"""()=>{{
          D.ship=[{{id:'s1',date:'2026-11-01',crop:'小松菜',store:{st!r},qty:10,price:100}}];
          D.moves=[{{id:'m1',date:'2026-11-05',type:'sold',crop:'小松菜',store:{st!r},qty:10,price:100}}];
          save();refreshAll();}}""")
        await pg.evaluate("openEdit('ship','s1')"); await pg.wait_for_timeout(350)
        await pg.fill('#eQty','3')
        await pg.click('#eOk'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("D.ship[0].qty")==10,'棚残がマイナスになる編集は止める')
        t('−7点' in await pg.inner_text('#toast'),'理由を出す: '+(await pg.inner_text('#toast')))
        await pg.fill('#eQty','12'); await pg.click('#eOk'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("D.ship[0].qty")==12,'問題なければ直せる')

        # ---- 4. 規格外 > 収穫量 ----
        await pg.evaluate("""()=>{D.plots=[{id:'p1',crop:'小松菜',name:'1',place:'ハウス',area:40,base:today(),
          steps:[{id:'x1',n:'収穫',date:today(),t:'収穫',m:60,done:false}]}];save();renderPlots();renderPlan()}""")
        await pg.evaluate("openSheet(allTasks().find(x=>x.sid==='x1'))"); await pg.wait_for_timeout(350)
        await pg.fill('#shGot','50'); await pg.fill('#shNg','80'); await pg.wait_for_timeout(300)
        t(await pg.is_disabled('#shOk'),'規格外が多いと保存できない')
        t('直してください' in await pg.inner_text('#shOk'),'ボタンの文言で知らせる')
        await pg.fill('#shNg','8'); await pg.wait_for_timeout(300)
        t(not await pg.is_disabled('#shOk'),'直せば押せる')
        await pg.click('#shOk'); await pg.wait_for_timeout(450)
        hv=await pg.evaluate("D.harv[0]")
        t(hv['got']==50 and hv['ng']==8,'値は丸められない '+str(hv))

        # ---- 5. 同じ日の二重出荷 ----
        await pg.evaluate("()=>{D.ship=[];D.moves=[];save();refreshAll()}")
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.click('#m-ship'); await pg.wait_for_timeout(300)
        await pg.click('#sCrop .chip:text-is("小松菜")'); await pg.wait_for_timeout(300)
        await pg.fill(f'[data-bsi="{st}"]','20'); await pg.wait_for_timeout(200)
        await pg.click('#sSave'); await pg.wait_for_timeout(450)
        t(await pg.evaluate("D.ship.length")==1,'1回目は保存できる')
        await pg.click('#sCrop .chip:text-is("小松菜")'); await pg.wait_for_timeout(300)
        hint=await pg.inner_text('#sHint')
        t('記録済み' in hint,'同日の記録があると知らせる: '+hint)
        await pg.fill(f'[data-bsi="{st}"]','20'); await pg.wait_for_timeout(200)
        await pg.click('#sSave'); await pg.wait_for_timeout(400)
        t(await pg.is_visible('#sheetC'),'二重出荷の確認が出る')
        await pg.click('#cNo'); await pg.wait_for_timeout(350)
        t(await pg.evaluate("D.ship.length")==1,'やめたら増えない')

        # ---- 6. 下書き ----
        await pg.fill(f'[data-bsi="{st}"]','33'); await pg.wait_for_timeout(700)
        d=await pg.evaluate("JSON.parse(localStorage.getItem('nokiroku:draft')||'null')")
        t(d and d['crop']=='小松菜' and d['qty'][st]==33,'入力が下書きに残る '+str(d and d['qty']))
        await pg.reload(); await pg.wait_for_timeout(700)
        t(await pg.is_visible('#sheetC'),'開き直すと続きを聞く')
        await pg.click('#cOk'); await pg.wait_for_timeout(500)
        t(await pg.evaluate("shipQty")=={st:33},'続きから入れられる')

        # ---- 7. 販売率 ----
        await pg.evaluate(f"""()=>{{
          D.ship=[{{id:'s1',date:'2026-11-01',crop:'小松菜',store:{st!r},qty:230,price:100}}];
          D.moves=[{{id:'m1',date:'2026-11-05',type:'sold',crop:'小松菜',store:{st!r},qty:186,price:100}},
                   {{id:'m2',date:'2026-11-06',type:'back',crop:'小松菜',store:{st!r},qty:18,price:100}}];
          uFrom='';uTo='';save();goto('p-sum');renderSum();}}""")
        await pg.wait_for_timeout(500)
        txt=await pg.inner_text('#uBody')
        t('販売率 81%' in txt,'持込ベースの販売率 81%')
        t('棚残 26点' in txt,'棚残も並べる')

        # ---- 8. 直販は店舗名にできない ----
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(300)
        await pg.fill('#storeNew','直販'); await pg.click('#storeAdd'); await pg.wait_for_timeout(350)
        t(await pg.evaluate("D.stores.includes('直販')")==False,'「直販」は店舗に登録できない')

        # ---- 9. 壊れたバックアップ ----
        bad=os.path.join(OUT,'bad2.json')
        json.dump({"app":"kanon","data":{"crops":["小松菜"],"stores":["A"],"tasks":["収穫"],
          "ship":[{"id":"x1","date":"2026-11-22","crop":"小松菜","store":"A",
                   "qty":"<img src=x onerror=\"window.__pwn=1\">","price":100}],
          "moves":[],"exp":[],"work":[],"spray":[],"fert":[],"harv":[],
          "plots":[{"id":"p9","crop":"小松菜","base":"2026-10-01"}]}},
          open(bad,'w',encoding='utf-8'),ensure_ascii=False)
        await pg.set_input_files('#bkFile',bad); await pg.wait_for_timeout(500)
        if await pg.is_visible('#sheetC'):
            await pg.click('#cOk'); await pg.wait_for_timeout(400)
        if await pg.is_visible('#sheetC'):
            await pg.click('#cOk'); await pg.wait_for_timeout(500)
        t(await pg.evaluate("window.__pwn")!=True,'仕込まれたスクリプトは動かない')
        t(await pg.evaluate("D.ship.length")==0,'形のおかしい行は取り除く')
        t(await pg.evaluate("(D.plots[0]&&Array.isArray(D.plots[0].steps))")==True,'工程なしの作型も壊れない')
        await pg.evaluate("goto('p-plan')"); await pg.wait_for_timeout(400)
        t(len(await pg.inner_text('#planBody'))>0,'予定タブが白紙にならない')
        t(len(errs)==0,'JSエラーなし')

        # ---- 10. まとめてずらす ----
        await pg.evaluate("""()=>{D.plots=[{id:'p1',crop:'小松菜',name:'1',place:'ハウス',area:40,base:today(),
          steps:[{id:'x1',n:'収穫',date:today(),t:'収穫',m:60,done:false}]}];save();renderPlots()}""")
        before=await pg.evaluate("D.plots[0].steps[0].date")
        await pg.evaluate("""()=>{const b=document.querySelector('[data-shift]');if(b)b.click()}""")
        await pg.wait_for_timeout(400)
        if await pg.is_visible('#cInput'):
            await pg.fill('#cInput','99999999'); await pg.click('#cOk'); await pg.wait_for_timeout(400)
            t(await pg.evaluate("D.plots[0].steps[0].date")==before,'大きすぎる日数は弾く')
        else: t(False,'まとめてずらすが開けない（未確認）')

        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
print('JSエラー:',len(errs)); [print(' ',e) for e in errs[:8]]
