# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import pathlib, json
import os, pathlib
# このテストが見にいく kanon 本体。既定はリポジトリの index.html。
# 別のファイルを試すときは KANON=/path/to/app.html python3 tests/t5.py
ROOT = pathlib.Path(__file__).resolve().parent.parent
APP  = os.environ.get("KANON", str(ROOT / "index.html"))
APPURL = "file://" + APP
OUTDIR = os.environ.get("KANON_OUT", str(ROOT / "tests" / "_shots"))
os.makedirs(OUTDIR, exist_ok=True)

APP=pathlib.Path(''+APP+'').resolve().as_uri()
errs=[]; fails=[]
def ck(c,l,d=''):
    print(('  OK   ' if c else '  FAIL ')+l+(('  '+str(d)) if d and not c else ''))
    if not c: fails.append(l)
def notoast(pg): pg.evaluate("()=>{const t=document.getElementById('toast');if(t)t.classList.remove('on','act')}")
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':390,'height':900})
    pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.on('console',lambda m: errs.append('console:'+m.text) if m.type=='error' else None)
    pg.goto(APP); pg.wait_for_timeout(900)

    print('--- 指摘された事例の再現 ---')
    pg.evaluate("""()=>{const t=today(),S=D.stores[0];
      D.ship=[{id:'a',date:addDays(t,-3),crop:'シュンギク',store:S,qty:100,price:300,left:null},
              {id:'b',date:addDays(t,-1),crop:'シュンギク',store:S,qty:10,price:100,left:null}];
      D.moves=[];save();}""")
    v=pg.evaluate("()=>shelfValue()")
    ck(v==31000,'棚の金額 300×100+100×10=31,000円',v)

    print('--- FIFOで消し込む ---')
    pg.click('nav button[data-p="p-rec"]'); pg.wait_for_timeout(200)
    pg.click('#m-rec'); pg.wait_for_timeout(700)
    ck('300円×100' in pg.locator('#rcBody').inner_text(),'単価の内訳が出る',pg.locator('#rcBody').inner_text()[:90].replace('\n',' '))
    # 110点すべて売る
    pg.locator('.sh-card input[data-k="sold"]').first.fill('110'); pg.wait_for_timeout(300)
    pg.click('#rcSave'); pg.wait_for_timeout(800); notoast(pg)
    mv=pg.evaluate("()=>D.moves.map(m=>[m.qty,m.price])")
    ck(mv==[[100,300],[10,100]],'単価ごとに2件に分かれる',json.dumps(mv))
    amt=pg.evaluate("()=>soldTotal()")
    ck(amt==31000,'売上 31,000円（誤った11,000円ではない）',amt)
    ck(pg.evaluate("()=>shelfValue()")==0,'棚は0円に')

    print('--- 一部だけ売る ---')
    pg.evaluate("""()=>{const t=today(),S=D.stores[0];
      D.ship=[{id:'a',date:addDays(t,-3),crop:'ハクサイ',store:S,qty:50,price:300,left:null},
              {id:'b',date:addDays(t,-1),crop:'ハクサイ',store:S,qty:50,price:200,left:null}];
      D.moves=[];save();}""")
    pg.evaluate("()=>renderRecover()"); pg.wait_for_timeout(500)
    pg.locator('.sh-card input[data-k="sold"]').first.fill('60'); pg.wait_for_timeout(300)
    pg.click('#rcSave'); pg.wait_for_timeout(800); notoast(pg)
    mv=pg.evaluate("()=>D.moves.map(m=>[m.qty,m.price])")
    ck(mv==[[50,300],[10,200]],'古いロットから消える 50@300 + 10@200',json.dumps(mv))
    ck(pg.evaluate("()=>soldTotal()")==17000,'売上 15,000+2,000=17,000円',pg.evaluate("()=>soldTotal()"))
    ck(pg.evaluate("()=>shelfValue()")==8000,'棚残 40点×200円=8,000円',pg.evaluate("()=>shelfValue()"))

    print('--- 在庫超過は全体を止める ---')
    pg.evaluate("""()=>{const t=today();
      D.ship=[{id:'a',date:t,crop:'シュンギク',store:D.stores[0],qty:10,price:180,left:null},
              {id:'b',date:t,crop:'小松菜',store:D.stores[0],qty:10,price:130,left:null}];
      D.moves=[];save();renderRecover();}""")
    pg.wait_for_timeout(500)
    cards=pg.locator('.sh-card')
    cards.nth(0).locator('input[data-k="sold"]').fill('5')
    cards.nth(1).locator('input[data-k="sold"]').fill('99'); pg.wait_for_timeout(300)
    pg.click('#rcSave'); pg.wait_for_timeout(700)
    ck(pg.evaluate("()=>D.moves.length")==0,'1件も保存されない（部分保存しない）',pg.evaluate("()=>D.moves.length"))
    ck('超えています' in pg.locator('#toast').inner_text(),'どの店のどの品目か出る',pg.locator('#toast').inner_text())
    notoast(pg)

    print('--- 取り消し ---')
    cards.nth(1).locator('input[data-k="sold"]').fill('5'); pg.wait_for_timeout(300)
    pg.click('#rcSave'); pg.wait_for_timeout(700)
    ck(pg.evaluate("()=>D.moves.length")==2,'2件保存')
    ck(pg.locator('.toast .undo').is_visible(),'取り消しが出る')
    pg.click('.toast .undo'); pg.wait_for_timeout(600)
    ck(pg.evaluate("()=>D.moves.length")==0,'取り消せる')
    b.close()
print('\nJSエラー:',len(errs))
for e in errs[:4]:print('  ',e[:130])
print('失敗:',fails or 'なし')
