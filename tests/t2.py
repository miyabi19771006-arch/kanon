# -*- coding: utf-8 -*-
import asyncio, json, os
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
URL=APPURL
ok=[];ng=[];errs=[]
def t(c,m):(ok if c else ng).append(m)

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844},accept_downloads=True)
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.on('console',lambda m:errs.append(m.text) if m.type=='error' else None)
        await pg.goto(URL); await pg.wait_for_timeout(500)

        # データを作る
        await pg.evaluate("""()=>{
          D.ship.push({id:'a1',date:today(),crop:'ベビーリーフ',store:D.stores[0],qty:100,price:300});
          D.work.push({id:'w1',date:today(),crop:'小松菜',task:'収穫',min:90,ppl:1});
          D.exp.push({id:'e1',date:today(),cat:'資材費',note:'袋',amt:1200});
          save();refreshAll();
        }""")
        # 設定へ
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(300)
        info=await pg.inner_text('#bkInfo')
        t('3件' in info, 'バックアップ件数の表示: '+info.replace('\n',' '))

        # 書き出し
        async with pg.expect_download() as dl:
            await pg.click('#bkSave')
        d=await dl.value
        path=os.path.join(OUT,'bk.json'); await d.save_as(path)
        t(d.suggested_filename.startswith('kanon-'),'ファイル名 '+d.suggested_filename)
        obj=json.load(open(path,encoding='utf-8'))
        t(obj.get('app')=='kanon' and len(obj['data']['ship'])==1,'中身が正しい')

        # 消去 → 空になる
        await pg.click('#wipe'); await pg.wait_for_timeout(250)
        await pg.click('#cOk'); await pg.wait_for_timeout(400)
        n=await pg.evaluate("D.ship.length+D.work.length+D.exp.length")
        t(n==0,'消去できた')
        # 消去後に品目追加ができる（旧バグ）
        await pg.fill('#cropNew','テスト菜')
        await pg.press('#cropNew','Enter'); await pg.wait_for_timeout(250)
        t(await pg.evaluate("D.crops.includes('テスト菜')"),'消去後も品目を追加できる')

        # 読み込み
        await pg.set_input_files('#bkFile',path); await pg.wait_for_timeout(400)
        await pg.click('#cOk'); await pg.wait_for_timeout(600)
        st=await pg.evaluate("[D.ship.length,D.work.length,D.exp.length]")
        t(st==[1,1,1],'読み込みで戻った '+str(st))
        # 画面にも反映されている
        await pg.evaluate("goto('p-rec')"); await pg.wait_for_timeout(300)
        t(await pg.evaluate("D.crops.includes('テスト菜')==false"),'読み込みで置きかわる')
        sh=await pg.evaluate("shelfValue()")
        t(sh==30000,'棚の金額が復活 '+str(sh))

        # 違うファイルは弾く
        bad=os.path.join(OUT,'bad.json');open(bad,'w').write('{"hello":1}')
        await pg.evaluate("goto('p-set')")
        await pg.set_input_files('#bkFile',bad); await pg.wait_for_timeout(400)
        tx=await pg.inner_text('#toast')
        t('kanon' in tx,'別のファイルは弾く: '+tx)

        # 保存失敗の帯
        await pg.evaluate("""()=>{
          S.set=async()=>({ok:false,err:new Error('full')});
          window.storage=undefined;
        }""")
        await pg.evaluate("save()"); await pg.wait_for_timeout(300)
        vis=await pg.is_visible('#saveErr')
        t(vis,'保存できないと帯が出る')
        if vis:
            t('保存できませんでした' in await pg.inner_text('#saveErr'),'帯の文言')

        await pg.screenshot(path=os.path.join(OUT,'set.png'),full_page=True)
        await b.close()

asyncio.run(main())
print('\n'.join('OK '+x for x in ok))
print('\n'.join('NG '+x for x in ng))
print('JSエラー:',len(errs), errs[:5] if errs else '')
