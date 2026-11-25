# -*- coding: utf-8 -*-
# スプレッドシートから取り込む（売上・経費）
#  ・既定はオフ。オフのあいだはボタンが見えない（友人の kanon に出ない）
#  ・取り込みURLとオン/オフは端末だけに置く。JSONバックアップに入らない
#  ・バックアップを戻しても、この機能はオンにならない
#  ・売上は記録済みの点数を差し引く。経費は同じ日・同じ金額を外しておく
#  ・二度読んでも二重にならない
import asyncio, os, json, pathlib
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
APP  = os.environ.get("KANON", str(ROOT / "index.html"))
APPURL = "file://" + APP
OUTDIR = os.environ.get("KANON_OUT", str(ROOT / "tests" / "_shots"))
os.makedirs(OUTDIR, exist_ok=True)
OUT = OUTDIR

ok = []; ng = []; errs = []
def t(c, m): (ok if c else ng).append(m)

URL = "https://script.google.com/macros/s/AKfycbTEST_kanon_0123456789abcdefXYZ/exec"

# Apps Script が返す形（実際のシートの中身＋確かめ用の行）
SHEET = {
  "app": "kanon-sheet", "ver": 1, "at": "2026-11-25T15:00:00+09:00",
  "sales": [
    {"row": 2, "date": "2026-11-23", "store": "道の駅おおさと", "seller": "佐藤 ふみ子", "item": "チンゲン菜",
     "kind": "農産物", "qty": 4, "price": 130, "amt": 520, "at": "18:46"},
    {"row": 3, "date": "2026-11-25", "store": "おてんとさん 大和店", "seller": "佐藤 ふみ子", "item": "枝豆【秘伝】",
     "kind": "農産物", "qty": 17, "price": 280, "amt": 4760, "at": "19:10"},
    {"row": 4, "date": "2026-07-29", "store": "元気くん市場仙台南店", "seller": "佐藤 雅彦", "item": "とうもろこし",
     "kind": "農産物", "qty": 16, "price": 420, "amt": 6720, "at": "14:46"},
    {"row": 5, "date": "2026-07-29", "store": "元気くん市場仙台南店", "seller": "佐藤 雅彦", "item": "とうもろこし",
     "kind": "農産物", "qty": 1, "price": 450, "amt": 450, "at": "14:46"},
    {"row": 6, "date": "2026-09-23", "store": "万葉・おおひら館", "seller": "佐藤 雅彦", "item": "工芸品",
     "kind": "雑収入", "qty": 1, "price": 450, "amt": 450, "at": "18:45"},
  ],
  "exp": [
    {"row": 2, "date": "2026-11-19", "cat": "諸材料費", "note": "カインズ古川店 ウォールライトWL100", "amt": 698, "src": "IMG_4435.JPG"},
    {"row": 3, "date": "2026-11-19", "cat": "種苗費", "note": "カインズ古川店 シャオパオ348円×3", "amt": "1,044", "src": "IMG_4435.JPG"},
    {"row": 4, "date": "2026-11-18", "cat": "動力光熱費", "note": "JA新みやぎ 大郷SS レギュラーガソリン6.50L", "amt": 1000, "src": "チャット添付"},
    {"row": 5, "date": "2026-11-20", "cat": "不明", "note": "なにかの部品", "amt": 330, "src": ""},
    {"row": 6, "date": "", "cat": "肥料費", "note": "日付なし", "amt": 500, "src": ""},
  ]
}

mode = {"v": "ok"}
async def handler(route):
    if mode["v"] == "ok":
        await route.fulfill(status=200, headers={"Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json"}, body=json.dumps(SHEET, ensure_ascii=False))
    elif mode["v"] == "html":
        await route.fulfill(status=200, headers={"Access-Control-Allow-Origin": "*",
            "Content-Type": "text/html"}, body="<html><body>Google ログイン</body></html>")
    elif mode["v"] == "err":
        await route.fulfill(status=200, headers={"Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json"},
            body=json.dumps({"app": "kanon-sheet", "ver": 1, "error": "シート「売上」が見つかりません"}, ensure_ascii=False))
    else:
        await route.abort()

async def vis(pg, sel):
    return await pg.evaluate(f"(()=>{{const e=document.querySelector({sel!r});return !!(e&&e.getClientRects().length)}})()")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2,
                                  color_scheme='dark', accept_downloads=True)
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        # つながらない場合をわざと作るので、その読み込み失敗だけは数えない
        pg.on('console', lambda m: errs.append('CON ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.route("https://script.google.com/**", handler)

        # ---- 1. 既定はオフ。ボタンは見えない ----
        await pg.goto(APPURL); await pg.wait_for_timeout(800)
        t(await pg.evaluate("gsOn()") == False, '既定はオフ')
        await pg.evaluate("goto('p-rec')"); await pg.evaluate("mode('m-rec')"); await pg.wait_for_timeout(300)
        t(not await vis(pg, '#gsOpenRec'), 'オフのとき販売に取り込みボタンが出ない')
        await pg.evaluate("mode('m-exp')"); await pg.wait_for_timeout(300)
        t(not await vis(pg, '#gsOpenExp'), 'オフのとき経費に取り込みボタンが出ない')
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(300)
        t(await pg.inner_text('#gsTog') == 'オフ', '設定の表示もオフ')
        t(not await vis(pg, '#gsUrl'), 'オフのときURL欄は出ない')

        # ---- 2. オンにしてURLを入れる ----
        await pg.click('#gsTog'); await pg.wait_for_timeout(300)
        t(await pg.inner_text('#gsTog') == 'オン', 'オンになる')
        t(await vis(pg, '#gsUrl'), 'URL欄が出る')
        await pg.fill('#gsUrl', 'https://example.com/steal'); await pg.click('#gsSave'); await pg.wait_for_timeout(250)
        t(not await pg.evaluate("gsConf().url"), '形の違うURLは保存しない')
        t(await pg.evaluate("$('fldGsUrl').classList.contains('bad')"), '形の違うURLは赤くなる')
        await pg.fill('#gsUrl', '  ' + URL + ' '); await pg.click('#gsSave'); await pg.wait_for_timeout(250)
        t(await pg.evaluate("gsConf().url") == URL, '正しいURLは前後の空白を落として保存')
        raw_d = await pg.evaluate("localStorage.getItem('nokiroku:v2')")
        t(URL not in raw_d and 'AKfycb' not in raw_d, 'URLは記録（nokiroku:v2）に入らない')
        t('AKfycb' not in json.dumps(await pg.evaluate("D"), ensure_ascii=False), 'D の中にもない')

        # ---- 3. バックアップにURLもオン/オフも入らない ----
        async with pg.expect_download() as di:
            await pg.click('#bkSave')
        dl = await di.value
        bk = os.path.join(OUT, 'gs_backup.json')
        await dl.save_as(bk)
        txt = open(bk, encoding='utf-8').read()
        t('AKfycb' not in txt and 'script.google.com' not in txt, 'バックアップにURLが入らない')
        t('kanon:gs' not in txt and '"gs' not in txt, 'バックアップに取り込みの設定が入らない')

        # ---- 4. 取り込み：準備（出荷・記録済みの売上・手で入れた経費） ----
        await pg.evaluate("""()=>{
          D.calias={'チンゲン菜':'チンゲンサイ','とうもろこし':'トウモロコシ'};
          D.ship=[{id:'s1',date:'2026-11-20',crop:'チンゲンサイ',store:'道の駅おおさと',qty:10,price:130},
                  {id:'s2',date:'2026-07-28',crop:'トウモロコシ',store:'元気くん市場仙台南店',qty:20,price:420}];
          D.moves=[{id:'m1',date:'2026-11-23',type:'sold',crop:'チンゲンサイ',store:'道の駅おおさと',qty:2,price:130},
                   {id:'m2',date:'2026-07-29',type:'sold',crop:'トウモロコシ',store:'元気くん市場仙台南店',qty:16,price:420}];
          D.exp=[{id:'x1',date:'2026-11-19',cat:'諸材料費',note:'カインズ古川店 ウォールライトWL100',amt:698}];
          save();refreshAll();}""")
        t(await pg.evaluate("simpStore('万葉・おおひら館')") == '万葉おおひら館', '中黒の有無が違っても同じ店とみなす')
        await pg.evaluate("goto('p-rec')"); await pg.evaluate("mode('m-exp')"); await pg.wait_for_timeout(300)
        t(await vis(pg, '#gsOpenExp'), 'オンのとき経費に取り込みボタンが出る')
        await pg.evaluate("mode('m-rec')"); await pg.wait_for_timeout(300)
        t(await vis(pg, '#gsOpenRec'), 'オンのとき販売にも出る')
        await pg.click('#gsOpenRec'); await pg.wait_for_timeout(900)
        t(await vis(pg, '#sheetGs'), '取り込みの画面が開く')
        prev = await pg.inner_text('#gsPrev')
        S = await pg.evaluate("gsSales.map(r=>({k:r.key,on:r.on,can:r.can,done:r.done,qty:r.qty,why:(r.why||[]).join('/')}))")
        E = await pg.evaluate("gsExp.map(r=>({k:r.key,on:r.on,can:r.can,st:r.st,cat:r.cat,amt:r.amt}))")
        s = {x['k']: x for x in S}; e = {x['k']: x for x in E}
        t(s['s0']['on'] and s['s0']['qty'] == 2, 'チンゲン菜：シート4点−記録済み2点→2点だけ入れる ' + str(s['s0']))
        t('シート4点' in prev and '記録済み2点' in prev, '差し引きの内訳が見える')
        t(not s['s1']['on'] and not s['s1']['can'] and '未登録' in s['s1']['why'], '枝豆は品目が未登録なので入れない ' + str(s['s1']))
        t(s['s2']['done'] and not s['s2']['on'], 'とうもろこし16点は取り込み済み')
        t(s['s3']['on'] and s['s3']['qty'] == 1, 'とうもろこし@450の1点は新しく入る ' + str(s['s3']))
        t(not s['s4']['on'] and not s['s4']['can'] and '雑収入' in prev, '雑収入（工芸品）は入れない')
        t(e['e0']['st'] == 'dup' and not e['e0']['on'], '手で入れた698円は「記録済みかも」で外してある')
        t('記録済みかも' in prev, '「記録済みかも」と出る')
        t(e['e1']['st'] == 'new' and e['e1']['on'] and e['e1']['amt'] == 1044, '1,044円（カンマ入り）は新しく入る')
        t(e['e2']['on'], 'ガソリン1,000円も入る')
        t(e['e3']['on'] and e['e3']['cat'] == '雑費' and '雑費にしました' in prev, '科目「不明」は雑費にして印を出す')
        t(e['e4']['st'] == 'bad' and not e['e4']['can'], '日付のない行は入れられない')
        t(await pg.inner_text('#gsOk') == '5件を取り込む', 'ボタンは5件 ' + await pg.inner_text('#gsOk'))
        await pg.screenshot(path=os.path.join(OUT, 'gs_prev.png'), full_page=False)

        # 付け外し（行のどこを押しても切り替わる）
        await pg.click('[data-gspick="e0"] .impn'); await pg.wait_for_timeout(200)
        t(await pg.evaluate("gsExp[0].on") and await pg.inner_text('#gsOk') == '6件を取り込む', '「記録済みかも」を押すと入れられる')
        await pg.click('[data-gspick="e0"]'); await pg.wait_for_timeout(200)
        t(not await pg.evaluate("gsExp[0].on"), 'もう一度押すと外れる')
        await pg.click('[data-gspick="s3"]'); await pg.wait_for_timeout(200)
        t(await pg.inner_text('#gsOk') == '4件を取り込む', '売上も外せる')
        await pg.click('[data-gspick="s3"]'); await pg.wait_for_timeout(200)
        t(await pg.inner_text('#gsOk') == '5件を取り込む', '売上を戻せる')
        t(await pg.evaluate("document.querySelector('[data-gspick=\"s2\"]')") is None, '取り込み済みは押せない（行もない）')
        # 科目の選び直し
        await pg.select_option('[data-gscat="e3"]', '農具費'); await pg.wait_for_timeout(200)
        t(await pg.evaluate("gsExp[3].cat") == '農具費' and await pg.evaluate("gsExp[3].on"), '科目を選び直しても外れない')
        # 取り込み済みを見る
        await pg.click('[data-gsdone]'); await pg.wait_for_timeout(200)
        t('取り込み済み' in await pg.inner_text('#gsPrev'), '取り込み済みも見られる')
        await pg.click('[data-gsdone]'); await pg.wait_for_timeout(200)

        # ---- 5. 取り込む ----
        await pg.click('#gsOk'); await pg.wait_for_timeout(500)
        t(not await vis(pg, '#sheetGs'), '取り込むと閉じる')
        mv = await pg.evaluate("D.moves.filter(m=>m.id!=='m1'&&m.id!=='m2').map(m=>[m.date,m.store,m.crop,m.qty,m.price])")
        t(sorted(mv) == sorted([['2026-11-23', '道の駅おおさと', 'チンゲンサイ', 2, 130],
                                ['2026-07-29', '元気くん市場仙台南店', 'トウモロコシ', 1, 450]]), '売上が2件入る ' + str(mv))
        ex = await pg.evaluate("D.exp.filter(x=>x.id!=='x1').map(x=>[x.date,x.cat,x.amt,!!x.gk])")
        t(sorted(ex) == sorted([['2026-11-19', '種苗費', 1044, True], ['2026-11-18', '動力光熱費', 1000, True],
                                ['2026-11-20', '農具費', 330, True]]), '経費が3件入る ' + str(ex))
        t('取り込みました' in await pg.inner_text('#toast'), '取り込んだと知らせる')
        t(await pg.evaluate("document.querySelector('#toast .undo')") is not None, '「取り消す」が出る')
        # 取り消すと売上も経費もまとめて戻る。そのあともう一度取り込む
        await pg.evaluate("undoLast()"); await pg.wait_for_timeout(300)
        t(await pg.evaluate("D.moves.length") == 2 and await pg.evaluate("D.exp.length") == 1, '取り消すと売上・経費とも元に戻る')
        await pg.click('#gsOpenRec'); await pg.wait_for_timeout(900)
        await pg.select_option('[data-gscat="e3"]', '農具費'); await pg.wait_for_timeout(200)
        await pg.click('#gsOk'); await pg.wait_for_timeout(500)
        t(await pg.evaluate("D.moves.length") == 4 and await pg.evaluate("D.exp.length") == 4, '取り込み直せる')

        # ---- 6. もう一度読んでも二重にならない ----
        await pg.click('#gsOpenRec'); await pg.wait_for_timeout(900)
        t(await pg.evaluate("gsSales.filter(r=>r.on).length+gsExp.filter(r=>r.on).length") == 0, '二度目は新しく入るものがない')
        t(not await vis(pg, '#gsOk'), '取り込むボタンも出ない')
        t(await pg.evaluate("gsExp.filter(r=>r.st==='done').length") == 3, '経費3件は「取り込み済み」とわかる')
        t('隠しています' in await pg.inner_text('#gsPrev'), '取り込み済みはたたんである')
        await pg.click('#gsCancel'); await pg.wait_for_timeout(300)


        # ---- 7. 失敗したとき ----
        mode["v"] = "html"
        await pg.click('#gsOpenRec'); await pg.wait_for_timeout(800)
        t('kanon用のスクリプトではない' in await pg.inner_text('#errGs'), 'ログイン画面などが返ったら知らせる')
        t(not await vis(pg, '#gsOk'), '失敗したら取り込むボタンは出ない')
        mode["v"] = "err"
        await pg.click('#gsFetch'); await pg.wait_for_timeout(800)
        t('シート「売上」が見つかりません' in await pg.inner_text('#errGs'), 'スクリプト側のエラーを伝える')
        mode["v"] = "abort"
        await pg.click('#gsFetch'); await pg.wait_for_timeout(800)
        t('つながりませんでした' in await pg.inner_text('#errGs'), 'つながらないとき知らせる')
        t('全員' in await pg.inner_text('#errGs'), '公開設定の確かめ方も書く')
        await pg.click('#gsCancel'); await pg.wait_for_timeout(300)
        mode["v"] = "ok"

        # ---- 8. URLを消すと、開いたときに設定へ案内する ----
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(300)
        await pg.click('#gsClear'); await pg.wait_for_timeout(300)
        await pg.click('#cOk'); await pg.wait_for_timeout(300)
        t(not await pg.evaluate("gsConf().url"), 'URLを消せる')
        t(await pg.evaluate("gsOn()"), 'URLを消してもオンのまま')
        await pg.evaluate("goto('p-rec')"); await pg.evaluate("mode('m-rec')"); await pg.wait_for_timeout(300)
        await pg.click('#gsOpenRec'); await pg.wait_for_timeout(400)
        t(await vis(pg, '#gsGoSet'), 'URLがないと「設定を開く」が出る')
        await pg.click('#gsGoSet'); await pg.wait_for_timeout(500)
        t(await pg.evaluate("document.querySelector('.panel.on').id") == 'p-set', '設定に移る')

        # ---- 9. オフに戻すとボタンが消える。開き直してもオフのまま ----
        await pg.fill('#gsUrl', URL); await pg.click('#gsSave'); await pg.wait_for_timeout(200)
        await pg.click('#gsTog'); await pg.wait_for_timeout(300)
        await pg.reload(); await pg.wait_for_timeout(800)
        t(await pg.evaluate("gsOn()") == False and await pg.evaluate("document.body.classList.contains('no-gs')"), '開き直してもオフ')
        t(await pg.evaluate("gsConf().url") == URL, 'オフにしてもURLは残る')
        await pg.evaluate("goto('p-rec')"); await pg.evaluate("mode('m-rec')"); await pg.wait_for_timeout(300)
        t(not await vis(pg, '#gsOpenRec'), 'オフに戻すとボタンが消える')

        # ---- 10. すべて消去でURLも消える ----
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(300)
        await pg.click('#wipe'); await pg.wait_for_timeout(300); await pg.click('#cOk'); await pg.wait_for_timeout(400)
        t(await pg.evaluate("localStorage.getItem('kanon:gs')") is None, 'すべて消去で取り込みURLも消える')

        # ---- 11. 友人の端末：バックアップを戻してもこの機能は出ない ----
        ctx2 = await b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
        p2 = await ctx2.new_page()
        p2.on('pageerror', lambda e: errs.append('友人: ' + str(e)))
        await p2.goto(APPURL); await p2.wait_for_timeout(800)
        await p2.evaluate("goto('p-set')"); await p2.wait_for_timeout(300)
        await p2.set_input_files('#bkFile', bk); await p2.wait_for_timeout(500)
        for _ in range(2):
            if await vis(p2, '#sheetC'):
                await p2.click('#cOk'); await p2.wait_for_timeout(500)
        t(await p2.evaluate("gsOn()") == False, '戻しても取り込みはオフのまま')
        t(await p2.evaluate("localStorage.getItem('kanon:gs')") is None, '友人の端末にURLは来ない')
        await p2.evaluate("goto('p-rec')"); await p2.evaluate("mode('m-exp')"); await p2.wait_for_timeout(300)
        t(not await vis(p2, '#gsOpenExp'), '友人の kanon にボタンは出ない')
        await ctx2.close()

        t(len(errs) == 0, 'JSエラーなし ' + str(errs[:3]))
        await b.close()

try: asyncio.run(main())
except Exception as ex: ng.append('途中で止まった: ' + str(ex).split(chr(10))[0])
ok[:] = [x for x in ok if x]
print('\n'.join('OK ' + x for x in ok)); print('\n'.join('NG ' + x for x in ng))
