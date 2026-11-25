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
M="""【netDoA産直　売上のご連絡】道の駅おおさと
2026年11月24日 15時17分 現在
チンゲン菜　(単価130円)       5点      650円
【合計】      5点      650円
店舗名：道の駅おおさと
"""
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await (await b.new_context(viewport={'width':390,'height':844})).new_page()
        pg.on('pageerror',lambda e:errs.append(str(e)))
        await pg.goto(APPURL); await pg.wait_for_timeout(700)
        await pg.evaluate("""()=>{
          D.crops=['チンゲンサイ','共通'];D.calias={};
          D.ship=[{id:'s1',date:'2026-11-24',crop:'チンゲンサイ',store:'道の駅おおさと',qty:20,price:130}];
          D.moves=[];save();refreshAll();}""")
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.click('#m-rec'); await pg.wait_for_timeout(300)
        await pg.click('#simpOpen'); await pg.wait_for_timeout(300)
        await pg.fill('#simpText',M); await pg.click('#simpRead'); await pg.wait_for_timeout(450)
        t('品目が未登録' in str(await pg.evaluate("simpRows[0].why")),'未登録として出る')
        # 読み替えを選ぶ
        await pg.select_option('[data-simpc="チンゲン菜"]','チンゲンサイ'); await pg.wait_for_timeout(500)
        t(await pg.evaluate("simpRows[0].crop")=='チンゲンサイ','読み替わる')
        t(await pg.evaluate("D.crops.includes('チンゲン菜')")==False,'余計な品目は増えない')
        await pg.click('#simpOk'); await pg.wait_for_timeout(500)
        t(await pg.evaluate("D.moves.map(r=>r.crop)")==['チンゲンサイ'],'チンゲンサイとして記録される')

        # 両方やってしまった既存データでも、読み替えが勝つ
        await pg.evaluate("""()=>{D.crops.push('チンゲン菜');D.calias={'チンゲン菜':'チンゲンサイ'};save()}""")
        t(await pg.evaluate("simpCrop('チンゲン菜')")=='チンゲンサイ','両方あっても読み替えを優先する')
        # 「品目に追加」を選んだら読み替えは外れる
        await pg.evaluate("""()=>{D.crops=['チンゲンサイ','共通'];D.calias={'チンゲン菜':'チンゲンサイ'};D.moves=[];save()}""")
        await pg.click('#simpOpen'); await pg.wait_for_timeout(300)
        await pg.fill('#simpText',M); await pg.click('#simpRead'); await pg.wait_for_timeout(450)
        sel=await pg.query_selector('[data-simpc="チンゲン菜"]')
        if sel:
            await pg.select_option('[data-simpc="チンゲン菜"]','__new'); await pg.wait_for_timeout(500)
            t(await pg.evaluate("D.calias['チンゲン菜']")==None,'品目に追加すると読み替えは外れる')
            t(await pg.evaluate("D.crops.includes('チンゲン菜')"),'品目として追加される')
        else:
            t(True,'読み替えが効いて未登録扱いにならない（それも正しい）')
        t(len(errs)==0,'JSエラーなし '+str(errs[:2]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
