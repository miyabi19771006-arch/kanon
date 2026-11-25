# -*- coding: utf-8 -*-
import asyncio,os,re
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

SEED="""()=>{
  D.fees={'道の駅おおさと':10};D.feeDefault=10;
  // 小松菜：古い作型（1〜3月、10a）と今の作型（10〜12月、20a）
  D.plots=[
    {id:'old',crop:'小松菜',name:'春',place:'露地',area:10,base:'2026-01-10',steps:[
      {id:'a1',n:'播種',date:'2026-01-10',t:'播種',m:60,done:true},
      {id:'a2',n:'収穫',date:'2026-03-20',t:'収穫',m:90,done:true}]},
    {id:'now',crop:'小松菜',name:'秋',place:'ハウス',area:20,base:'2026-10-01',steps:[
      {id:'b1',n:'播種',date:'2026-10-01',t:'播種',m:60,done:true},
      {id:'b2',n:'収穫',date:'2026-12-10',t:'収穫',m:90,done:false}]}
  ];
  // 11月の売上 100,000円（手数料10% = 10,000円）、作業 10時間、経費 30,000円
  D.ship=[{id:'s1',date:'2026-11-05',crop:'小松菜',store:'道の駅おおさと',qty:500,price:200}];
  D.moves=[{id:'m1',date:'2026-11-06',type:'sold',crop:'小松菜',store:'道の駅おおさと',qty:500,price:200}];
  D.work=[{id:'w1',date:'2026-11-06',crop:'小松菜',task:'収穫',min:600,ppl:1}];
  D.exp=[{id:'e1',date:'2026-11-06',cat:'資材費',note:'培土',amt:30000}];
  save();
}"""

def num(txt,label):
    # 「label 12,345円」のような並びから数字を取る
    m=re.search(label+r'[^0-9\-]{0,12}(-?[\d,]+)',txt)
    return int(m.group(1).replace(',','')) if m else None

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844})
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append('PAGE '+str(e)))
        pg.on('console',lambda m:errs.append('CON '+m.text) if m.type=='error' else None)
        await pg.goto(APPURL); await pg.wait_for_timeout(500)
        await pg.evaluate("()=>{D.adv=true;D.plotOn=true;save();applyFeat()}"); await pg.wait_for_timeout(200)
        await pg.evaluate(SEED); await pg.reload(); await pg.wait_for_timeout(600)

        # 期間＝2026年11月
        await pg.evaluate("()=>{uFrom='2026-11';uTo='2026-11';goto('p-sum');renderSum()}")
        await pg.wait_for_timeout(500)
        txt=await pg.inner_text('#uBody')

        # 差引 = 100,000 - (30,000 + 10,000手数料) = 60,000
        t(num(txt,'差引')==60000,'差引 60,000円 → '+str(num(txt,'差引')))
        # 時給 = 60,000 / 10時間 = 6,000円（売上ベースなら10,000円）
        hz=num(txt,'時給')
        t(hz==6000,'時給は差引ベース 6,000円 → '+str(hz))
        t('売上だけで割ると 10,000円' in txt,'売上ベースも添える')

        # 面積：11月にかかるのは秋（ハウス20a）だけ。春の10aは入らない
        vals=await pg.evaluate("""()=>{
          const r={};D.plots.forEach(p=>r[p.name]=plotInRange(p));return r;}""")
        t(vals=={'春':False,'秋':True},'11月にかかる作型だけ '+str(vals))
        row=[l for l in txt.split('\n') if l.startswith('小松菜')]
        t('20a' in txt and '30a' not in txt,'面積は20a（30aにならない）')
        # 10aあたり = (100,000-10,000) / 20a * 10 = 45,000円
        t('45,000' in txt,'10aあたり 45,000円 → '+str([l for l in txt.split('\n') if '45,000' in l]))
        # 品目別の時給 = 90,000 / 10時間 = 9,000円
        t('9,000' in txt,'品目別の時給は手数料を引いて 9,000円')
        t('かかっている作型' in txt,'期間でしぼった説明が出る')

        # 期間＝2026年1〜3月 → 春の10aだけ
        await pg.evaluate("()=>{uFrom='2026-01';uTo='2026-03';renderSum()}"); await pg.wait_for_timeout(400)
        vals=await pg.evaluate("""()=>{const r={};D.plots.forEach(p=>r[p.name]=plotInRange(p));return r;}""")
        t(vals=={'春':True,'秋':False},'1〜3月は春だけ '+str(vals))

        # 全期間 → 両方
        await pg.evaluate("()=>{uFrom='';uTo='';renderSum()}"); await pg.wait_for_timeout(400)
        vals=await pg.evaluate("""()=>{const r={};D.plots.forEach(p=>r[p.name]=plotInRange(p));return r;}""")
        t(vals=={'春':True,'秋':True},'全期間は両方 '+str(vals))
        txt=await pg.inner_text('#uBody')
        t('30a' in txt,'全期間なら30a（春＋秋）')

        # 露地とハウス：11月はハウスだけ
        await pg.evaluate("()=>{uFrom='2026-11';uTo='2026-11';renderSum()}"); await pg.wait_for_timeout(400)
        txt=await pg.inner_text('#uBody')
        i=txt.find('露地とハウス')
        seg=txt[i:i+300] if i>=0 else ''
        t('ハウス' in seg and '露地' not in seg.replace('露地とハウス',''),'11月はハウスだけ出る: '+seg.replace('\n',' / ')[:120])

        # 作業時間ゼロのとき
        await pg.evaluate("()=>{D.work=[];save();renderSum()}"); await pg.wait_for_timeout(400)
        txt=await pg.inner_text('#uBody')
        t('—' in txt,'作業時間0でも落ちない')

        await pg.evaluate("()=>{D.work=[{id:'w1',date:'2026-11-06',crop:'小松菜',task:'収穫',min:600,ppl:1}];save();renderSum()}")
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=os.path.join(OUT,'sum6.png'),full_page=True)
        await b.close()
try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
print('JSエラー:',len(errs)); [print(' ',e) for e in errs[:6]]
