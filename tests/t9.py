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
        ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,
            color_scheme='dark',permissions=['clipboard-read','clipboard-write'])
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append('PAGE '+str(e)))
        await pg.goto(APPURL); await pg.wait_for_timeout(600)
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(250)
        await pg.click('#m-exp'); await pg.wait_for_timeout(250)
        await pg.click('#impOpen'); await pg.wait_for_timeout(350)

        await pg.click('#impCopy'); await pg.wait_for_timeout(400)
        lbl=await pg.inner_text('#impCopy')
        t('コピーしました' in lbl,'ボタン自体が知らせる: '+lbl)
        cb=await pg.evaluate("navigator.clipboard.readText().catch(()=>'')")
        t('YYYY-MM-DD' in cb,'中身もコピーされている')

        # トーストがシートの上に出ているか（実際に一番手前にあるか）
        z=await pg.evaluate("[getComputedStyle($('toast')).zIndex,getComputedStyle(document.querySelector('.sheet.on')).zIndex]")
        t(int(z[0])>int(z[1]),'トーストがシートより上（toast '+str(z[0])+' / sheet '+str(z[1])+'）')
        t(await pg.evaluate("$('toast').classList.contains('on')&&+getComputedStyle($('toast')).opacity===1"),'トーストが見えている')
        await pg.screenshot(path=os.path.join(OUT,'imp_copy.png'))

        # ラベルが戻る
        await pg.wait_for_timeout(2800)
        t('読み取りのお願い文をコピー' in await pg.inner_text('#impCopy'),'少しで元に戻る')

        # シートの中の別のお知らせも見えるか
        await pg.fill('#impText','')
        await pg.click('#impRead'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("$('toast').classList.contains('on')") and '貼り付けて' in await pg.inner_text('#toast'),'「貼り付けてから押して」も見える')

        # 確認ダイアログ（z-index 60）より上か
        await pg.evaluate("void ask('たしかめ','本文','はい',true)"); await pg.wait_for_timeout(350)
        await pg.evaluate("toast('重なりの確認')"); await pg.wait_for_timeout(350)
        zz=await pg.evaluate("[getComputedStyle($('toast')).zIndex,getComputedStyle($('sheetC')).zIndex]")
        t(int(zz[0])>int(zz[1]),'確認ダイアログより上（toast '+str(zz[0])+' / 確認 '+str(zz[1])+'）')
        # 取り消すボタンがダイアログの上に残らないこと
        await pg.evaluate("()=>{$('sheetC').classList.remove('on')}")
        await pg.evaluate("()=>{lastAdd=[{arr:'exp',id:'x'}];toast('消せます',true)}"); await pg.wait_for_timeout(300)
        t(await pg.evaluate("$('toast').classList.contains('on')&&!!$('toast').querySelector('.undo')"),'取り消すが出ている')
        await pg.evaluate("void ask('たしかめ2','本文','はい',true)"); await pg.wait_for_timeout(400)
        shown=await pg.evaluate("$('toast').classList.contains('on')")
        t(not shown,'ダイアログが開くと前のトーストは消える')
        t(await pg.is_visible('#cOk'),'ダイアログのボタンが押せる状態')
        await pg.screenshot(path=os.path.join(OUT,'imp_over.png'))
        t(len(errs)==0,'JSエラーなし '+str(errs[:2]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
