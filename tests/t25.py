# -*- coding: utf-8 -*-
# 追加した4科目が、入力・取り込み・集計のどこでも使えるか
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
NEW=['雇人費','利子割引料','土地改良費','素畜費']
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

        cats=await pg.evaluate("()=>CATS")
        for c in NEW: t(c in cats, c+' が科目にある')
        t(cats[-1]=='雑費','雑費は最後のまま')
        t(len(cats)==18,'科目は18 '+str(len(cats)))
        t(len(set(cats))==18,'重複なし')

        # ① 経費の入力画面にチップが出る
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.evaluate("()=>mode('m-exp')"); await pg.wait_for_timeout(400)
        chips=await pg.evaluate("""()=>[...document.querySelectorAll('#xpCat .chip,#xpCat button')].map(b=>b.textContent.trim())""")
        for c in NEW: t(c in chips, c+' のボタンが出る')

        # ② 手入力で保存できる
        await pg.evaluate("""()=>{sel.xcrop=null;renderForms()}""")
        n0=await pg.evaluate("()=>D.exp.length")
        await pg.evaluate("""(c)=>{const b=[...document.querySelectorAll('#xpCat .chip,#xpCat button')]
            .find(x=>x.textContent.trim()===c); b.click();}""",'雇人費')
        await pg.wait_for_timeout(300)
        await pg.fill('#xpAmt','50000')
        await pg.evaluate("()=>$('xpSave').click()"); await pg.wait_for_timeout(600)
        t(await pg.evaluate("()=>D.exp.length")==n0+1,'雇人費で1件保存できる')
        t(await pg.evaluate("()=>D.exp[D.exp.length-1].cat")=='雇人費','科目が雇人費で入る')

        # ③ 貼り付けでも読める（マークダウン）
        MD=("| 2026-11-20 | 雇人費 | 手伝い 日当 | 8000 |\n"
            "| 2026-11-20 | 利子割引料 | JA 借入利息 | 1200 |\n"
            "| 2026-11-21 | 土地改良費 | 大郷土地改良区 賦課金 | 15000 |\n"
            "| 2026-11-21 | 素畜費 | ひな 10羽 | 3000 |\n"
            "| 合計 | 27200 |")
        r=await pg.evaluate("(t)=>{const a=impParse(t);return {n:a.length,total:a.total,cats:a.map(x=>x.cat),guess:a.filter(x=>x.guess).length}}",MD)
        t(r['n']==4,'4件に分かれる '+str(r['n']))
        t(r['cats']==NEW,'4科目とも読める '+str(r['cats']))
        t(r['guess']==0,'どれも推測あつかいにならない')
        t(r['total']==27200,'合計も拾う')

        # ④ お願い文の科目一覧に入っている
        pr=await pg.evaluate("()=>impPrompt()")
        for c in NEW: t(c in pr, 'お願い文に '+c+' がある')

        # ⑤ 集計に出る
        await pg.evaluate("""()=>{D.exp.push({id:'n1',date:today(),cat:'土地改良費',note:'賦課金',amt:15000});
            uFrom='';uTo='';save();refreshAll();renderSum()}""")
        await pg.evaluate("goto('p-sum')"); await pg.wait_for_timeout(600)
        sm=await pg.inner_text('#uBody')
        t('土地改良費' in sm,'集計にも出る')
        await pg.screenshot(path=os.path.join(OUT,'cats18.png'),full_page=True)
        # ⑥ 旧名「土地改良区費」で入っていた記録を直す
        await pg.evaluate("""()=>{const d=JSON.parse(localStorage.getItem('nokiroku:v2'));
          d.exp.push({id:'old1',date:'2026-11-21',cat:'土地改良区費',note:'賦課金',amt:15000});
          d.seed=5;localStorage.setItem('nokiroku:v2',JSON.stringify(d))}""")
        await pg.reload(); await pg.wait_for_timeout(900)
        old=await pg.evaluate("()=>D.exp.filter(x=>x.cat==='土地改良区費').length")
        neo=await pg.evaluate("()=>D.exp.filter(x=>x.id==='old1')[0].cat")
        t(old==0,'旧名が残っていない')
        t(neo=='土地改良費','土地改良費に直っている '+str(neo))
        t(await pg.evaluate("()=>D.seed")>=6,'seedが6以上 '+str(await pg.evaluate("()=>D.seed")))
        t(await pg.evaluate("()=>D.exp.filter(x=>x.id==='old1')[0].amt")==15000,'金額は変わらない')

        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
