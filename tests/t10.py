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

M1 = """【netDoA産直　売上のご連絡】道の駅おおさと
佐藤　ふみ子様

2026年11月22日 15時17分 現在

店舗は現在営業中です。現時点の売上速報です。
通信状況により実績は前後しますので予めご了承ください。

商品名                                                点 数   売上金額  
--------------------------------------------------------------------------
小松菜　(単価100円)       1点      100円
手芸品　(単価1000円)      1点     1000円
水菜　(単価100円)                1点      100円
レタス　(単価100円)       2点      200円
--------------------------------------------------------------------------
【合計】      5点     1400円

※このメールは送信専用ですので、メールを返信されませんようお願いします。
店舗名：道の駅おおさと
"""
# 同じ日の後続メール（累計が増えている）
M2 = M1.replace('15時17分','18時05分').replace('小松菜　(単価100円)       1点      100円',
                                               '小松菜　(単価100円)       4点      400円').replace('【合計】      5点     1400円','【合計】      8点     1700円')

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,color_scheme='dark')
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append('PAGE '+str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(600)

        # 棚に在庫を作る（小松菜・水菜・レタスを道の駅おおさとへ）
        await pg.evaluate("""()=>{
          ['小松菜','水菜','レタス'].forEach(c=>{if(!D.crops.includes(c))D.crops.splice(D.crops.indexOf('共通'),0,c)});
          [['小松菜',20,100],['水菜',10,100],['レタス',10,100]].forEach((x,i)=>
            D.ship.push({id:'q'+i,date:'2026-11-21',crop:x[0],store:'道の駅おおさと',qty:x[1],price:x[2]}));
          save();refreshAll();}""")
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(250)
        await pg.click('#m-rec'); await pg.wait_for_timeout(300)
        await pg.click('#simpOpen'); await pg.wait_for_timeout(350)
        t(await pg.is_visible('#sheetSimp'),'シートが開く')

        # 1通だけ
        await pg.fill('#simpText',M1)
        await pg.click('#simpRead'); await pg.wait_for_timeout(450)
        rows=await pg.evaluate("simpRows.map(r=>[r.rawCrop,r.store,r.qty,r.price,r.skip,r.why])")
        for r in rows: print('  ',r)
        t(len(rows)==4,'4品目を読む '+str(len(rows)))
        t(rows[0][:4]==['小松菜','道の駅おおさと',1,100],'品目・店舗・点数・単価 '+str(rows[0][:4]))
        t(rows[1][4]==True and '品目が未登録' in rows[1][5],'手芸品は未登録として弾く')
        txt=await pg.inner_text('#simpPrev')
        t('3件' in txt and '400円' in txt,'合計は手芸品を除く: '+txt.split(chr(10))[0])
        t('15:17 時点' in txt,'時刻が出る')

        # 累計メール2通 → 新しいほうだけ
        await pg.fill('#simpText',M1+"\n"+M2)
        await pg.click('#simpRead'); await pg.wait_for_timeout(450)
        rows=await pg.evaluate("simpRows.map(r=>[r.rawCrop,r.qty,r.at])")
        t(all(r[2]=='18:05' for r in rows),'古い速報は使わない '+str(set(r[2] for r in rows)))
        km=[r for r in rows if r[0]=='小松菜'][0]
        t(km[1]==4,'最後の累計を使う（1点ではなく4点）'+str(km[1]))
        t('古い速報メール1通は使いません' in await pg.inner_text('#simpPrev'),'その旨を出す')

        # 取り込む
        await pg.click('#simpOk'); await pg.wait_for_timeout(500)
        mv=await pg.evaluate("D.moves.map(r=>[r.date,r.store,r.crop,r.qty,r.price,r.type])")
        t(len(mv)==3,'3件入る '+str(mv))
        t(sum(r[3]*r[4] for r in mv)==700,'売上 700円 '+str(sum(r[3]*r[4] for r in mv)))
        t(all(r[0]=='2026-11-22' for r in mv),'日付はメールの日')

        # もう一度同じものを貼る → 取り込み済みで弾く
        await pg.click('#simpOpen'); await pg.wait_for_timeout(300)
        await pg.fill('#simpText',M2)
        await pg.click('#simpRead'); await pg.wait_for_timeout(450)
        sk=await pg.evaluate("simpRows.filter(r=>r.skip).length")
        t(sk==4,'二度目は全部飛ばす '+str(sk))
        t('取り込み済み' in await pg.inner_text('#simpPrev'),'取り込み済みと出る')
        t(await pg.is_visible('#simpOk')==False,'取り込むボタンが出ない')

        # 棚より多い
        await pg.fill('#simpText',M1.replace('レタス　(単価100円)       2点      200円','レタス　(単価100円)       99点     9900円').replace('2026年11月22日 15時17分','2026年11月23日 15時17分'))
        await pg.click('#simpRead'); await pg.wait_for_timeout(450)
        w=await pg.evaluate("simpRows.filter(r=>r.rawCrop==='レタス')[0].why")
        t(any('棚に' in x for x in w),'棚不足を弾く '+str(w))

        # 店名のゆらぎ（全角スペースや「店」の有無）
        await pg.evaluate("()=>{D.stores.push('おてんとさん 大和店');save()}")
        await pg.fill('#simpText',M1.replace('道の駅おおさと','おてんとさん　大和').replace('11月22日','11月24日'))
        await pg.click('#simpRead'); await pg.wait_for_timeout(450)
        st=await pg.evaluate("simpRows[0].store")
        t(st=='おてんとさん 大和店','店名のゆらぎを合わせる -> '+str(st))

        t(len(errs)==0,'JSエラーなし '+str(errs[:2]))
        await pg.fill('#simpText',M1.replace('11月22日','11月25日'))
        await pg.click('#simpRead'); await pg.wait_for_timeout(500)
        await pg.screenshot(path=os.path.join(OUT,'simp.png'),full_page=True)
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
print('JSエラー:',len(errs)); [print(' ',e) for e in errs[:5]]
