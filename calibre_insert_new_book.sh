#!/usr/bin/env sh

# https://manual.calibre-ebook.com/generated/en/calibredb.html
# https://stackoverflow.com/questions/15580144/how-to-concatenate-multiple-lines-of-output-to-one-line
calibredb add `find epub/ -maxdepth 1 -type f -iname '*.epub' -mtime -1 | tr '\n' ' '`
