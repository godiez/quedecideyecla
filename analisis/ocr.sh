#!/bin/bash
# uso: ocr.sh <doc>   (p. ej. 2021-01-07_JGL_01)
set -e
d=$1; y=${d:0:4}; org=$(echo $d | cut -d_ -f2 | tr A-Z a-z)
pdf=data/pdfs/$org/$y/$d.pdf
tmp=$(mktemp -d); pdftoppm -r 300 -gray -png "$pdf" $tmp/p
out=analisis/$y/txt/$d.txt; : > $out.new
for p in $tmp/p*.png; do OMP_THREAD_LIMIT=1 tesseract $p - -l spa --psm 1 2>/dev/null >> $out.new; printf '\f' >> $out.new; done
mv $out.new $out; rm -rf $tmp; echo "$d $(wc -w < $out)"
