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

PASTE = """2026-11-05\t諸材料費\tホームセンター山新 培土20L\t3480
2026-11-08\t肥料費\tJAグリーン 化成肥料20kg\t12,600
11/12\t農薬衛生費\tダコニール1000\t2980
2026/11/15\t種苗費\t○○種苗店 ベビーリーフ種\t¥8,200
2026-11-18\tよくわからない科目\t謎の店\t1500
2026-11-20\t農具費\tレジ印字かすれ\t読めない
ただの文章です"""

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844},
            permissions=['clipboard-read','clipboard-write'])
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append('PAGE '+str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(600)

        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(250)
        await pg.click('#m-exp'); await pg.wait_for_timeout(300)
        await pg.click('#impOpen'); await pg.wait_for_timeout(350)
        t(await pg.is_visible('#sheetImp'),'取り込みシートが開く')

        # お願い文
        await pg.click('#impCopy'); await pg.wait_for_timeout(350)
        cb=await pg.evaluate("navigator.clipboard.readText().catch(()=>'')")
        t('YYYY-MM-DD' in cb and '諸材料費' in cb and '税込' in cb,'お願い文がコピーされる('+str(len(cb))+'文字)')
        t('雑費' in cb and CATS_OK(cb),'科目の一覧が入っている')

        # 空で押す
        await pg.fill('#impText','')
        await pg.click('#impRead'); await pg.wait_for_timeout(300)
        t('貼り付けて' in await pg.inner_text('#toast'),'空なら知らせる')

        # 読み取り
        await pg.fill('#impText',PASTE)
        await pg.click('#impRead'); await pg.wait_for_timeout(450)
        rows=await pg.evaluate("impRows.map(r=>[r.date,r.cat,r.note,r.amt,r.bad])")
        for r in rows: print('  ',r)
        t(rows[0][:4]==['2026-11-05','諸材料費','ホームセンター山新 培土20L',3480],'タブ区切り '+str(rows[0][:4]))
        t(rows[1][3]==12600,'カンマ入りの金額 '+str(rows[1][3]))
        t(rows[2][0]=='2026-11-12','月日だけなら今年 '+str(rows[2][0]))
        t(rows[3][3]==8200 and rows[3][0]=='2026-11-15','¥とスラッシュ日付 '+str(rows[3][:1]+rows[3][3:4]))
        t(rows[4][1]=='雑費','知らない科目は雑費に')
        t(len(rows[5][4])>0,'金額が読めない行に印 '+str(rows[5][4]))

        txt=await pg.inner_text('#impPrev')
        t('読めない行' in txt,'読めない行の数を出す')
        t('28,760' in txt,'取り込める合計 '+[l for l in txt.split('\n') if '円' in l][0])

        # 科目の選び直し
        await pg.select_option('[data-impcat="4"]','動力光熱費'); await pg.wait_for_timeout(250)
        t(await pg.evaluate("impRows[4].cat")=='動力光熱費','科目を選び直せる')

        # 取り込む
        before=await pg.evaluate("D.exp.length")
        label=await pg.inner_text('#impOk')
        t('件を取り込む' in label,'件数がボタンに出る: '+label)
        await pg.click('#impOk'); await pg.wait_for_timeout(500)
        after=await pg.evaluate("D.exp.map(r=>[r.date,r.cat,r.amt])")
        t(len(after)-before==5,'読めた5件だけ入る '+str(len(after)-before))
        t(not await pg.is_visible('#sheetImp'),'シートが閉じる')
        t(await pg.evaluate("D.exp.reduce((a,r)=>a+r.amt,0)")==28760,'合計が合う')

        # 取り消し
        await pg.click('#toast .undo'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("D.exp.length")==before,'まとめて取り消せる')

        # 重複の印
        await pg.evaluate("()=>{D.exp.push({id:'d1',date:'2026-11-05',cat:'諸材料費',note:'先に入れた',amt:3480});save()}")
        await pg.click('#impOpen'); await pg.wait_for_timeout(300)
        await pg.fill('#impText',PASTE)
        await pg.click('#impRead'); await pg.wait_for_timeout(400)
        t('重複かも' in await pg.inner_text('#impPrev'),'同じ日・同じ金額に印が付く')

        # 既存データを消さない
        await pg.click('#impOk'); await pg.wait_for_timeout(450)
        t(await pg.evaluate("D.exp.some(r=>r.note==='先に入れた')"),'既存の記録は残る')

        t(len(errs)==0,'JSエラーなし '+str(errs[:2]))
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.click('#m-exp'); await pg.click('#impOpen'); await pg.wait_for_timeout(300)
        await pg.fill('#impText',PASTE); await pg.click('#impRead'); await pg.wait_for_timeout(500)
        await pg.screenshot(path=os.path.join(OUT,'imp.png'),full_page=True)
        await b.close()

def CATS_OK(cb): return cb.count('／')>=10
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
print('JSエラー:',len(errs)); [print(' ',e) for e in errs[:5]]
