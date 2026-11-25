# -*- coding: utf-8 -*-
# 消えたトーストの「取り消す」が、見えないまま押せてしまわないか
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
        ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,color_scheme='dark')
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(800)

        # 出荷を1件保存 → 取り消すトーストが出る
        await pg.evaluate("""()=>{lastUndo=()=>{window.__undone=true};toast('テスト',true)}""")
        await pg.wait_for_timeout(300)
        t(await pg.evaluate("()=>$('toast').classList.contains('on')"),'トーストが出ている')
        pe=await pg.evaluate("""()=>getComputedStyle($('toast').querySelector('.undo')).pointerEvents""")
        t(pe=='auto','見えているときは押せる')

        # 消えたあと（on が外れたあと）
        await pg.evaluate("""()=>{$('toast').classList.remove('on')}"""); await pg.wait_for_timeout(200)
        pe2=await pg.evaluate("""()=>getComputedStyle($('toast').querySelector('.undo')).pointerEvents""")
        t(pe2=='none','消えたら押せない（透明な当たり判定が残らない）')
        hit=await pg.evaluate("""()=>{const r=$('toast').querySelector('.undo').getBoundingClientRect();
          const el=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
          return el?el.className+'|'+el.tagName:'none'}""")
        t('undo' not in str(hit),'その場所を押しても取り消すに当たらない '+str(hit))

        # シートが開いたら取り消しの中身まで捨てる
        await pg.evaluate("""()=>{window.__undone=false;lastUndo=()=>{window.__undone=true};toast('テスト2',true)}""")
        await pg.wait_for_timeout(250)
        await pg.evaluate("""()=>{$('sheetC').classList.add('on')}"""); await pg.wait_for_timeout(300)
        t(await pg.evaluate("()=>!$('toast').classList.contains('on')"),'シートが開くとトーストが消える')
        t(await pg.evaluate("()=>lastUndo===null"),'取り消しの中身も捨てている')
        await pg.evaluate("""()=>{$('sheetC').classList.remove('on')}""")
        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
