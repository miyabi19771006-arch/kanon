#!/usr/bin/env bash
# kanon のテストを全部走らせる。
#   bash tests/run.sh              → リポジトリの index.html を試す
#   KANON=/path/app.html bash tests/run.sh → 別のファイルを試す
cd "$(dirname "$0")/.." || exit 1
ng=0
for f in smoke t_lot t2 t3 t4 t5 t6 t7 t8 t9 t10 t11 t13 t14 t15 t16 t17 t18 t19 t20 t21 t22 t23 t24 t25; do
  [ -f "tests/$f.py" ] || continue
  r=$(python3 "tests/$f.py" 2>&1)
  n=$(echo "$r" | grep -cE '^ *NG|^失敗: [^な]')
  o=$(echo "$r" | grep -cE '^ *OK')
  printf '%-7s OK=%-3s NG=%s\n' "$f" "$o" "$n"
  if [ "$n" != "0" ]; then echo "$r" | grep -E '^ *NG|^失敗'; ng=$((ng+n)); fi
done
echo "----"
if [ "$ng" = "0" ]; then echo "ぜんぶ通りました"; else echo "NG が $ng 件あります"; exit 1; fi
