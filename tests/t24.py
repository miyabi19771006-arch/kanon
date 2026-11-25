# -*- coding: utf-8 -*-
# 経費の貼り付け：伝票を分ける／科目が読めないときに黙って雑費にしない
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
REAL=("2026-11-18\t動力光熱費\tJA新みやぎ 大郷SS レギュラーガソリン6.50L\t1000\n"
      "2026-11-19\t雑費\tカインズ古川店 ウォールライトWL100・シャオパオ×3\t　1742")
SPLIT=("2026-11-19\t肥料費\tカインズ古川店 配合肥料\t1200\n"
       "2026-11-19\t作業用衣料費\tカインズ古川店 軍手\t540")
BAD  =("2026-11-19\t消耗品費\tカインズ古川店 ウォールライト\t1100\n"
       "2026-11-20\tカインズ古川店 ねじ\t320")
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,color_scheme='dark')
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(800)

        # ① 実際の貼り付けデータ（全角スペース混じり）
        r=await pg.evaluate("(t)=>impParse(t).map(x=>[x.date,x.cat,x.amt,x.bad.length,!!x.guess])",REAL)
        t(r[0]==['2026-11-18','動力光熱費',1000,0,False],'1行目 '+str(r[0]))
        t(r[1]==['2026-11-19','雑費',1742,0,False],'2行目・全角スペースも読める '+str(r[1]))

        # ② 同じ伝票を科目で2行に分けられる
        r2=await pg.evaluate("(t)=>impParse(t).map(x=>[x.date,x.cat,x.amt,impDup(x)])",SPLIT)
        t(r2[0]==['2026-11-19','肥料費',1200,False] and r2[1]==['2026-11-19','作業用衣料費',540,False],
          '同じ日に2科目で分けられる '+str(r2))

        # ③ 決算書にない科目／科目なしは、雑費にしたことを知らせる
        r3=await pg.evaluate("(t)=>impParse(t).map(x=>[x.cat,!!x.guess,x.note])",BAD)
        t(r3[0][0]=='雑費' and r3[0][1]==True,'消耗品費は雑費にして印をつける '+str(r3[0]))
        t('消耗品費' in r3[0][2],'元の言葉は摘要に残す '+str(r3[0][2]))
        t(r3[1][0]=='雑費' and r3[1][1]==True,'科目なしも印をつける '+str(r3[1]))

        # ④ 画面に出るか
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.evaluate("()=>mode('m-exp')"); await pg.wait_for_timeout(300)
        await pg.evaluate("(t)=>{impRows=impParse(t);document.getElementById('sheetImp').classList.add('on');renderImpPrev()}",BAD)
        await pg.wait_for_timeout(400)
        pv=await pg.inner_text('#impPrev')
        t('科目は雑費にしました' in pv,'行に印が出る')
        t('2件あります' in pv,'まとめても知らせる')
        await pg.screenshot(path=os.path.join(OUT,'exp_guess.png'),full_page=True)

        # ⑤ 選び直すと印が消える
        await pg.select_option('[data-impcat="0"]','諸材料費'); await pg.wait_for_timeout(400)
        pv2=await pg.inner_text('#impPrev')
        t(pv2.count('科目は雑費にしました')==1,'直した行の印だけ消える')
        t('1件あります' in pv2,'残りの件数に直る')
        t(await pg.evaluate("()=>impRows[0].cat")=='諸材料費','選んだ科目が入る')

        # ⑥ ちゃんと取り込める
        n0=await pg.evaluate("()=>D.exp.length")
        await pg.evaluate("()=>$('impOk').click()"); await pg.wait_for_timeout(600)
        n1=await pg.evaluate("()=>D.exp.length")
        t(n1-n0==2,'2件入る '+str(n1-n0))
        cats=await pg.evaluate("()=>D.exp.slice(-2).map(x=>x.cat).sort()")
        t(cats==['諸材料費','雑費'],'科目もそのとおり '+str(cats))
        # ⑦ コピーして送る文章が「品目ごとに1行」と言っているか
        pr=await pg.evaluate("()=>impPrompt()")
        t('品目ごとに1行' in pr,'品目ごとに1行と書いてある')
        t('まとめないでください' in pr,'科目が同じでもまとめるなと書いてある')
        t('1行にまとめてください。品目ごとに分けないで' not in pr,'前の逆の指示が消えている')
        t('合計と一致することを必ず確かめて' in pr,'足し算の検算を指示している')
        t('不明' in pr and 'あてずっぽうで 雑費 にしないで' in pr,'分からないものは不明と書かせる')
        t(pr.count('| 2026-11-19 |')==2,'例も2行に分かれている '+str(pr.count('| 2026-11-19 |')))

        # ⑧ 科目「不明」は雑費にしたうえで必ず印をつける
        r4=await pg.evaluate("()=>impParse('2026-11-19\t不明\tカインズ なにか\t500').map(x=>[x.cat,!!x.guess,x.note])")
        t(r4[0][0]=='雑費' and r4[0][1]==True,'不明は雑費＋印 '+str(r4[0]))
        t('不明' in r4[0][2],'「不明」の字も摘要に残る')

        # ⑨ コピーで改行が消えてしまった貼り付け
        FLAT=("2026-11-19 諸材料費 カインズ古川店 ウォールライトWL100 698 "
              "2026-11-19 種苗費 カインズ古川店 シャオパオ 348円×3 1044 "
              "2026-11-18 動力光熱費 JA新みやぎ大郷SS レギュラーガソリン 154円×6.50L 1000")
        r5=await pg.evaluate("(t)=>impParse(t).map(x=>[x.date,x.cat,x.amt,x.bad.length])",FLAT)
        t(len(r5)==3,'改行が消えても3件に分かれる '+str(len(r5)))
        t(r5[0]==['2026-11-19','諸材料費',698,0],'1件目 '+str(r5[0]))
        t(r5[1]==['2026-11-19','種苗費',1044,0],'2件目 '+str(r5[1]))
        t(r5[2]==['2026-11-18','動力光熱費',1000,0],'3件目 '+str(r5[2]))
        t(sum(x[2] for x in r5)==2742,'合計も合う')

        # 正しく貼れている場合は何も変わらない
        TAB=("2026-11-19\t諸材料費\tカインズ古川店 ウォールライトWL100\t698\n"
             "2026-11-19\t種苗費\tカインズ古川店 シャオパオ 348円×3\t1044")
        r6=await pg.evaluate("(t)=>impParse(t).map(x=>[x.date,x.cat,x.amt,x.note])",TAB)
        t(len(r6)==2 and r6[0][3]=='カインズ古川店 ウォールライトWL100','正しい貼り付けは変わらない '+str(r6))

        # 摘要の中の日付で切らない（うしろに空白がなければ）
        r7=await pg.evaluate("()=>impParse('2026-11-19\t諸材料費\tカインズ 11/19納品のライト\t698').length")
        t(r7==1,'摘要の中の日付では切らない '+str(r7))

        # ⑩ 見出し行を飛ばす
        HEAD="日付\t科目\t摘要\t金額\n2026-11-18\t動力光熱費\tJA 給油\t1000"
        r8=await pg.evaluate("(t)=>impParse(t).map(x=>[x.date,x.amt])",HEAD)
        t(len(r8)==1 and r8[0]==['2026-11-18',1000],'見出し行を飛ばす '+str(r8))

        # ⑪ マークダウンの表
        MD=("| 日付 | 科目 | 支払先と品名 | 金額 |\n|---|---|---|---|\n"
            "| 2026-11-19 | 諸材料費 | カインズ古川店 ウォールライトWL100 | 698 |\n"
            "| 2026-11-19 | 種苗費 | カインズ古川店 シャオパオ348円×3 | 1044 |\n"
            "| 2026-11-18 | 動力光熱費 | JA大郷SS ガソリン | 1000 |")
        r9=await pg.evaluate("(t)=>impParse(t).map(x=>[x.date,x.cat,x.amt,x.bad.length])",MD)
        t(len(r9)==3,'マークダウンの表を読める '+str(len(r9)))
        t(r9[1]==['2026-11-19','種苗費',1044,0],'表の中身も正しい '+str(r9[1]))
        r10=await pg.evaluate("(t)=>impParse(t).length",MD.replace("\n"," "))
        t(r10==3,'改行が消えた表も読める '+str(r10))

        # ⑫ 合計で検算する
        OK3=("2026-11-19\t諸材料費\tカインズ ライト\t698\n"
             "2026-11-18\t動力光熱費\tJA ガソリン\t1000\n合計\t1698")
        rr=await pg.evaluate("(t)=>{const a=impParse(t);return [a.length,a.total]}",OK3)
        t(rr==[2,1698],'合計行は記録にせず検算に使う '+str(rr))
        rf=await pg.evaluate("(t)=>{const a=impParse(t.replace(/[\\n\\t]/g,' '));return [a.length,a.total]}",OK3)
        t(rf==[2,1698],'改行が消えても合計を拾う '+str(rf))

        await pg.evaluate("(t)=>{impRows=impParse(t);document.getElementById('sheetImp').classList.add('on');renderImpPrev()}",OK3)
        await pg.wait_for_timeout(300)
        t('合計が合いません' not in await pg.inner_text('#impPrev'),'合っていれば何も言わない')

        NG=("2026-11-19\t諸材料費\tカインズ ライト\t698\n合計\t1742")
        await pg.evaluate("(t)=>{impRows=impParse(t);renderImpPrev()}",NG); await pg.wait_for_timeout(300)
        pv3=await pg.inner_text('#impPrev')
        t('合計が合いません' in pv3,'合わなければ赤で知らせる')
        t('1,742円' in pv3 and '698円' in pv3,'両方の金額を出す')
        t('読み落としがあります' in pv3,'どちらに食い違うかも言う')

        # 合計を書かない貼り付けは、これまでどおり何も言わない
        await pg.evaluate("()=>{impRows=impParse('2026-11-19\\t諸材料費\\tカインズ ライト\\t698');renderImpPrev()}")
        await pg.wait_for_timeout(300)
        t('合計が合いません' not in await pg.inner_text('#impPrev'),'合計なしなら何も言わない')

        # お願い文にも合計を足したか
        pr2=await pg.evaluate("()=>impPrompt()")
        t('| 合計 | 全部を足した数字 |' in pr2,'お願い文が合計行を求めている')
        t('| 合計 | 1742 |' in pr2,'例にも合計行がある')
        t('マークダウンの表だけを返して' in pr2,'マークダウンで返すよう頼んでいる')
        t('| 日付 | 科目 | 支払先と品名 | 金額 |' in pr2,'表の見出しを示している')
        t('|---|---|---|---|' in pr2,'区切り行も示している')
        t('タブ区切り' not in pr2,'前のタブ区切りの指示が消えている')
        # お願い文の例を、そのまま読み取れるか（文と実装が食い違わないように）
        ex=pr2.split('例（1枚の伝票に2品あった場合）\n')[1]
        rex=await pg.evaluate("(t)=>{const a=impParse(t);return [a.length,a.total,a.reduce((s,x)=>s+x.amt,0),a.filter(x=>x.bad.length).length]}",ex)
        t(rex==[2,1742,1742,0],'お願い文の例がそのまま通る '+str(rex))

        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
