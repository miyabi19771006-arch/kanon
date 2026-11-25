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
def mail(qty,amt,at='15時17分'):
    return f"""【netDoA産直　売上のご連絡】道の駅おおさと
2026年11月24日 {at} 現在
商品名                      点 数   売上金額
--------------------------------------------
ベビーリーフ　(単価150円)       {qty}点      {amt}円
--------------------------------------------
【合計】      {qty}点      {amt}円
店舗名：道の駅おおさと
"""
CORN = """【新みやぎサービス】本日の売上状況
営業日
2026年11月24日
19時14分 現在
<元気くん市場仙台南店>
トウモロコシ/佐藤　雅彦（420円)
    19点   7,980円
トウモロコシ/佐藤　雅彦 (450円)
     1点     450円
【合計】
    20点   8,430円
"""
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await (await b.new_context(viewport={'width':390,'height':844})).new_page()
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(700)
        await pg.evaluate("""()=>{
          if(!D.crops.includes('トウモロコシ'))D.crops.push('トウモロコシ');
          D.ship=[{id:'s1',date:'2026-11-24',crop:'ベビーリーフ',store:'道の駅おおさと',qty:40,price:150},
                  {id:'s2',date:'2026-11-24',crop:'トウモロコシ',store:'元気くん市場仙台南店',qty:30,price:420}];
          D.moves=[{id:'m1',date:'2026-11-24',type:'sold',crop:'ベビーリーフ',store:'道の駅おおさと',qty:4,price:150}];
          save();refreshAll();}""")
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(200)
        await pg.click('#m-rec'); await pg.wait_for_timeout(300)

        async def imp(txt):
            await pg.click('#simpOpen'); await pg.wait_for_timeout(300)
            await pg.fill('#simpText',txt); await pg.click('#simpRead'); await pg.wait_for_timeout(450)
            rows=await pg.evaluate("simpRows.map(r=>[r.crop,r.mailQty,r.done,r.qty,r.price,r.skip,r.why])")
            prev=await pg.inner_text('#simpPrev')
            if await pg.is_visible('#simpOk'): await pg.click('#simpOk'); await pg.wait_for_timeout(500)
            else: await pg.click('#simpCancel'); await pg.wait_for_timeout(300)
            return rows,prev
        sold=lambda: pg.evaluate("D.moves.filter(x=>x.type==='sold'&&x.crop==='ベビーリーフ').reduce((a,x)=>a+x.qty,0)")

        # 手入力4点 + メール6点 → 差額2点
        r,prev=await imp(mail(6,900))
        t(r[0][1:5]==[6,4,2,150],'累計6点・記録済み4点 → 2点だけ足す '+str(r[0][1:5]))
        t(await sold()==6,'合計が6点になる '+str(await sold()))
        t('記録済み4点' in prev,'画面にも差し引きを出す')

        # 夕方の速報17点 → さらに11点
        r,prev=await imp(mail(17,2550,'19時02分'))
        t(r[0][3]==11,'夕方の累計17点 → 11点を足す '+str(r[0][3]))
        t(await sold()==17,'合計17点 '+str(await sold()))

        # 同じメールをもう一度 → 何も足さない
        r,prev=await imp(mail(17,2550,'19時02分'))
        t(r[0][5]==True and '取り込み済み' in str(r[0][6]),'同じメールは二重にならない')
        t(await sold()==17,'17点のまま '+str(await sold()))

        # 記録のほうが多いとき
        await pg.evaluate("()=>{D.moves.push({id:'mx',date:'2026-11-24',type:'sold',crop:'ベビーリーフ',store:'道の駅おおさと',qty:5,price:150});save();refreshAll()}")
        r,prev=await imp(mail(17,2550,'20時00分'))
        t('記録のほうが' in prev,'記録超過を知らせる')
        t(await sold()==22,'勝手に減らさない '+str(await sold()))

        # 単価違い2行の累計
        await pg.evaluate("()=>{D.moves=D.moves.filter(x=>x.crop!=='トウモロコシ');D.moves.push({id:'c1',date:'2026-11-24',type:'sold',crop:'トウモロコシ',store:'元気くん市場仙台南店',qty:10,price:420});save();refreshAll()}")
        r,prev=await imp(CORN)
        t([x[3] for x in r]==[9,1],'単価違いも差額で（19-10=9、1）'+str([x[3] for x in r]))
        tot=await pg.evaluate("D.moves.filter(x=>x.crop==='トウモロコシ').reduce((a,x)=>a+x.qty,0)")
        t(tot==20,'合計20点 '+str(tot))

        # ＋−で画面が飛ばない
        await pg.click('#m-ship'); await pg.wait_for_timeout(350)
        await pg.click('#sCrop .chip'); await pg.wait_for_timeout(300)
        sts=await pg.evaluate("D.stores")
        await pg.fill(f'[data-bsi="{sts[0]}"]','5'); await pg.wait_for_timeout(200)
        await pg.evaluate("window.scrollTo(0,400)"); await pg.wait_for_timeout(300)
        y0=await pg.evaluate("scrollY")
        await pg.click(f'[data-bsq="{sts[2]}"][data-d="1"]')
        await pg.click(f'[data-bsq="{sts[2]}"][data-d="1"]'); await pg.wait_for_timeout(350)
        y1=await pg.evaluate("scrollY")
        t(abs(y1-y0)<5,f'＋を押しても画面が動かない {y0}→{y1}')
        t(await pg.evaluate(f"shipQty[{sts[2]!r}]")==2,'＋は効いている')
        t(await pg.evaluate(f"shipQty[{sts[0]!r}]")==5,'他の行の入力も残る')
        v=await pg.input_value(f'[data-bsi="{sts[2]}"]')
        t(v=='2','その行の表示も変わる '+v)
        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
