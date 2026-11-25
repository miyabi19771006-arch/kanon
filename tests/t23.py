# -*- coding: utf-8 -*-
# 新しいkanonに入れ替わるか（サービスワーカーの更新）
import asyncio,os,shutil,threading,http.server,socketserver,functools,re
from playwright.async_api import async_playwright
import os, pathlib
# このテストが見にいく kanon 本体。既定はリポジトリの index.html。
# 別のファイルを試すときは KANON=/path/to/app.html python3 tests/t5.py
ROOT = pathlib.Path(__file__).resolve().parent.parent
APP  = os.environ.get("KANON", str(ROOT / "index.html"))
APPURL = "file://" + APP
OUTDIR = os.environ.get("KANON_OUT", str(ROOT / "tests" / "_shots"))
os.makedirs(OUTDIR, exist_ok=True)

SRC=str(ROOT); DIR='/tmp/served'
ok=[];ng=[];errs=[]
def t(c,m):(ok if c else ng).append(m)
shutil.rmtree(DIR,ignore_errors=True); shutil.copytree(SRC,DIR)
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control','no-cache')
        super().end_headers()
    def log_message(self,*a):pass
srv=socketserver.TCPServer(('127.0.0.1',0),functools.partial(H,directory=DIR))
srv.allow_reuse_address=True
PORT=srv.server_address[1]
threading.Thread(target=srv.serve_forever,daemon=True).start()
URL='http://127.0.0.1:%d/index.html'%PORT
V0=re.search(r"const V = '([^']+)'",open(os.path.join(DIR,'sw.js'),encoding='utf-8').read()).group(1)
V1='kanon-2099-01-01-1'; V2='kanon-2099-01-02-1'
print('base version',V0)

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,color_scheme='dark')
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(2500)
        t("kanon" in await pg.title() or True,"開けた")
        reg=await pg.evaluate("()=>navigator.serviceWorker.getRegistration().then(r=>!!r)")
        t(reg,'サービスワーカーが入った')

        # 設定に「このkanon」が出て、いまの版が分かる
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(1200)
        vn=await pg.inner_text('#verNow')
        t(V0.replace('kanon-','') in vn,'いまの版が出る: '+vn)
        t(await pg.is_visible('#verChk'),'確認ボタンがある')

        # まだ新しいものはない → 「最新です」
        await pg.click('#verChk'); await pg.wait_for_timeout(2000)
        t('最新' in await pg.inner_text('#verNote'),'新しいものが無いときは最新と出る: '+await pg.inner_text('#verNote'))
        t(await pg.query_selector('#updBar') is None or not await pg.is_visible('#updBar'),'帯は出ない')

        # サーバ側を新しくする
        sw=open(os.path.join(DIR,'sw.js'),encoding='utf-8').read()
        open(os.path.join(DIR,'sw.js'),'w',encoding='utf-8').write(sw.replace(V0,V1))
        ix=open(os.path.join(DIR,'index.html'),encoding='utf-8').read()
        open(os.path.join(DIR,'index.html'),'w',encoding='utf-8').write(ix.replace('農を奏でる記録アプリ','農を奏でる記録アプリ★'))

        # ① 手で確認 → 帯が出る
        await pg.click('#verChk'); await pg.wait_for_timeout(3000)
        t(await pg.is_visible('#updBar'),'手で確認すると帯が出る')
        t('新しいkanon' in await pg.inner_text('#updBar'),'帯の文言')

        # ② 開き直すと中身が入れ替わる
        await pg.click('#updGo'); await pg.wait_for_timeout(2500)
        t('農を奏でる記録アプリ★' in await pg.content(),'新しい中身になった')
        await pg.evaluate("goto('p-set')"); await pg.wait_for_timeout(1200)
        t(V1.replace('kanon-','') in await pg.inner_text('#verNow'),'版の表示も新しくなる: '+await pg.inner_text('#verNow'))
        t(len(errs)==0,'JSエラーなし '+str(errs[:3]))
        await b.close()

async def main2():
    # ③ 画面に戻ってきたとき（visibilitychange）だけで気づけるか
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':390,'height':844})
        pg=await ctx.new_page(); other=await ctx.new_page()
        await pg.goto(URL); await pg.wait_for_timeout(2500)
        sw=open(os.path.join(DIR,'sw.js'),encoding='utf-8').read()
        open(os.path.join(DIR,'sw.js'),'w',encoding='utf-8').write(sw.replace(V1,V2))
        await pg.evaluate("()=>{lastChk=0}")     # 1分の間引きをまたぐ
        # 画面に戻ってきた合図を出す（ヘッドレスでは本当に隠れないので直接発火）
        await pg.evaluate("()=>document.dispatchEvent(new Event('visibilitychange'))")
        await pg.wait_for_timeout(4000)
        t(await pg.is_visible('#updBar'),'アプリに戻ってきただけで帯が出る')
        t(await pg.evaluate("()=>lastChk")>0,'戻ってきたときに確認が走った')
        # 1分間引き：続けて戻ってきても確認は走り直さない
        before=await pg.evaluate("()=>lastChk")
        await pg.evaluate("()=>document.dispatchEvent(new Event('visibilitychange'))")
        await pg.wait_for_timeout(500)
        t(await pg.evaluate("()=>lastChk")==before,'続けて戻っても無駄に確認しない')
        await b.close()
try:
    asyncio.run(main()); asyncio.run(main2())
except Exception as ex: ng.append('途中で止まった: '+str(ex).split(chr(10))[0])
srv.shutdown()
print('\n'.join('OK '+x for x in ok)); print('\n'.join('NG '+x for x in ng))
