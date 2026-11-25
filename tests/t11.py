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

A = """【netDoA産直　売上のご連絡】道の駅おおさと
佐藤　ふみ子様

2026年11月22日 15時17分 現在

商品名                                                点 数   売上金額  
--------------------------------------------------------------------------
小松菜　(単価100円)       1点      100円
水菜　(単価100円)                1点      100円
--------------------------------------------------------------------------
【合計】      2点      200円
店舗名：道の駅おおさと
"""
B = """産直売上情報
佐藤　ふみ子様の本日 19:10現在の売上情報をお知らせします。

------------------
枝豆【秘伝】
 17点   4,760円
------------------
【合　計】
 17点   4,760円


あじわいの朝大和店
022-345-8010
taiwa@xs614920.xsrv.jp
"""
C = """【新みやぎサービス】本日の売上状況

佐藤　雅彦様
本日の売上状況です。

営業日
2026年07月29日
19時14分 現在

<元気くん市場仙台南店>
とうもろこし/佐藤　雅彦（420円)
    19点   7,980円
とうもろこし/佐藤　雅彦 (450円)
     1点     450円
------------------
【小計】
    20点   8,430円
------------------
【合計】
    20点   8,430円

※このメールは送信専用ですので、メールを返信されませんようお願いします。
"""

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,color_scheme='dark')
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append('PAGE '+str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(600)
        await pg.evaluate("""()=>{
          ['小松菜','水菜','枝豆'].forEach(c=>{if(!D.crops.includes(c))D.crops.splice(D.crops.indexOf('共通'),0,c)});
          D.stores=['道の駅おおさと','元気くん市場仙台南店','おてんとさん 大和店','万葉おおひら館'];
          [['小松菜','道の駅おおさと',20,100],['水菜','道の駅おおさと',20,100],
           ['枝豆','おてんとさん 大和店',30,280],
           ['トウモロコシ','元気くん市場仙台南店',15,420],['トウモロコシ','元気くん市場仙台南店',10,450]
          ].forEach((x,i)=>D.ship.push({id:'q'+i,date:'2026-07-01',crop:x[0],store:x[1],qty:x[2],price:x[3]}));
          save();refreshAll();}""")
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(250)
        await pg.click('#m-rec'); await pg.wait_for_timeout(300)
        await pg.click('#simpOpen'); await pg.wait_for_timeout(350)

        # ---- 形式A ----
        await pg.fill('#simpText',A); await pg.click('#simpRead'); await pg.wait_for_timeout(400)
        r=await pg.evaluate("simpRows.map(x=>[x.rawCrop,x.store,x.qty,x.price,x.skip])")
        t(r==[['小松菜','道の駅おおさと',1,100,False],['水菜','道の駅おおさと',1,100,False]],'A netDoA '+str(r))

        # ---- 形式B（日付なし・単価なし・店名は末尾）----
        await pg.fill('#simpDate','2026-07-29')
        await pg.fill('#simpText',B); await pg.click('#simpRead'); await pg.wait_for_timeout(400)
        r=await pg.evaluate("simpRows.map(x=>[x.rawCrop,x.rawStore,x.store,x.qty,x.price,x.date,x.guessed,x.why])")
        print('  B:',r)
        t(len(r)==1 and r[0][0]=='枝豆【秘伝】','B 品名を拾う')
        t(r[0][3]==17 and r[0][4]==280,'B 単価は金額÷点数で280円 '+str(r[0][4]))
        t(r[0][1]=='あじわいの朝大和店','B 店名は末尾から '+str(r[0][1]))
        t(r[0][5]=='2026-07-29' and r[0][6]==True,'B 日付は指定したもの '+str(r[0][5]))
        t('店舗が未登録' in r[0][7],'B 店舗は読み替えが必要')

        # 読み替えを選ぶ
        await pg.select_option('[data-simps="あじわいの朝大和店"]','おてんとさん 大和店'); await pg.wait_for_timeout(450)
        r=await pg.evaluate("simpRows.map(x=>[x.store,x.why])")
        t(r[0][0]=='おてんとさん 大和店','店の読み替えが効く '+str(r[0]))
        t(await pg.evaluate("D.alias['あじわいの朝大和店']")=='おてんとさん 大和店','読み替えを覚える')
        t('品目が未登録' not in str(r[0][1]),'枝豆【秘伝】→枝豆 に自動で当たる '+str(r[0][1]))
        await pg.click('#simpOk'); await pg.wait_for_timeout(450)
        mv=await pg.evaluate("D.moves.map(x=>[x.store,x.crop,x.qty,x.price])")
        t(mv==[['おてんとさん 大和店','枝豆',17,280]],'B 取り込める '+str(mv))

        # ---- 形式C（店名は<>・生産者名つき・単価違い2行）----
        await pg.click('#simpOpen'); await pg.wait_for_timeout(300)
        await pg.fill('#simpText',C); await pg.click('#simpRead'); await pg.wait_for_timeout(400)
        r=await pg.evaluate("simpRows.map(x=>[x.rawCrop,x.store,x.qty,x.price,x.date,x.why])")
        print('  C:',r)
        t(len(r)==2,'C 2行に分かれる '+str(len(r)))
        t(all(x[0]=='とうもろこし' for x in r),'C 生産者名を落とす '+str(r[0][0]))
        t(r[0][1]=='元気くん市場仙台南店','C 店名は<>から '+str(r[0][1]))
        t([x[2] for x in r]==[19,1] and [x[3] for x in r]==[420,450],'C 単価違いを別に '+str([(x[2],x[3]) for x in r]))
        t(r[0][4]=='2026-07-29','C 営業日の日付 '+str(r[0][4]))
        t('品目が未登録' in str(r[0][5]),'C とうもろこし は未登録（登録名はトウモロコシ）')
        await pg.select_option('[data-simpc="とうもろこし"]','トウモロコシ'); await pg.wait_for_timeout(450)
        r=await pg.evaluate("simpRows.map(x=>[x.crop,x.skip])")
        t(all(x[0]=='トウモロコシ' and not x[1] for x in r),'品目の読み替えが2行とも効く '+str(r))
        await pg.click('#simpOk'); await pg.wait_for_timeout(450)
        mv=await pg.evaluate("D.moves.filter(x=>x.crop==='トウモロコシ').map(x=>[x.qty,x.price])")
        t(sum(a*b for a,b in mv)==8430,'C 売上 8,430円 '+str(mv))

        # ---- 3通まとめて ----
        await pg.evaluate("()=>{D.moves=[];save();refreshAll()}")
        await pg.click('#simpOpen'); await pg.wait_for_timeout(300)
        await pg.fill('#simpDate','2026-07-29')
        await pg.fill('#simpText',A+"\n"+B+"\n"+C); await pg.click('#simpRead'); await pg.wait_for_timeout(450)
        r=await pg.evaluate("simpRows.filter(x=>!x.skip).length")
        t(r==5,'3通まとめて5行 '+str(r))
        sto=await pg.evaluate("[...new Set(simpRows.map(x=>x.store))]")
        t(len(sto)==3,'3店に分かれる '+str(sto))
        await pg.click('#simpOk'); await pg.wait_for_timeout(500)
        tot=await pg.evaluate("D.moves.reduce((a,x)=>a+x.qty*x.price,0)")
        t(tot==13390,'合計 '+str(tot)+'円（200+4760+8430=13390）')
        t(len(errs)==0,'JSエラーなし '+str(errs[:2]))
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))

# ---- 単純な並び（日付 店舗 品目 点数 単価）----
import asyncio as _a
from playwright.async_api import async_playwright as _p
TSV = """2026-11-20\t道の駅おおさと\t小松菜\t5\t100
2026-11-20\t道の駅おおさと\t水菜\t3\t100
2026-11-20\tおてんとさん 大和店\t枝豆\t4\t280
11/21\t元気くん市場仙台南店\tトウモロコシ\t2\t450"""
ok2=[];ng2=[];e2=[]
def t2(c,m):(ok2 if c else ng2).append(m)
async def main2():
    async with _p() as p:
        b=await p.chromium.launch()
        pg=await (await b.new_context(viewport={'width':390,'height':844})).new_page()
        pg.on('pageerror',lambda e:e2.append(str(e)))
        await pg.goto(APPURL); await pg.wait_for_timeout(600)
        await pg.evaluate("""()=>{
          ['小松菜','水菜','枝豆'].forEach(c=>{if(!D.crops.includes(c))D.crops.splice(D.crops.indexOf('共通'),0,c)});
          D.stores=['道の駅おおさと','元気くん市場仙台南店','おてんとさん 大和店'];
          [['小松菜','道の駅おおさと',20,100],['水菜','道の駅おおさと',20,100],
           ['枝豆','おてんとさん 大和店',30,280],['トウモロコシ','元気くん市場仙台南店',10,450]
          ].forEach((x,i)=>D.ship.push({id:'q'+i,date:'2026-11-01',crop:x[0],store:x[1],qty:x[2],price:x[3]}));
          save();refreshAll();}""")
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(250)
        await pg.click('#m-rec'); await pg.wait_for_timeout(250)
        await pg.click('#simpOpen'); await pg.wait_for_timeout(300)
        await pg.fill('#simpText',TSV); await pg.click('#simpRead'); await pg.wait_for_timeout(450)
        r=await pg.evaluate("simpRows.map(x=>[x.date,x.store,x.crop,x.qty,x.price,x.skip])")
        for x in r: print('  ',x)
        t2(len(r)==4,'4行読む '+str(len(r)))
        t2(all(not x[5] for x in r),'全部取り込める')
        t2(r[3][0]=='2026-11-21','年なしの日付も読む '+str(r[3][0]))
        await pg.click('#simpOk'); await pg.wait_for_timeout(450)
        tot=await pg.evaluate("D.moves.reduce((a,x)=>a+x.qty*x.price,0)")
        t2(tot==500+300+1120+900,'合計 '+str(tot)+'円')
        t2(len(e2)==0,'JSエラーなし '+str(e2[:2]))
        await b.close()
_a.run(main2())
print('\n'.join('OK '+x for x in ok2)); print('\n'.join('NG '+x for x in ng2))
