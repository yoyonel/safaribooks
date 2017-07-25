#!/usr/bin/env sh

# https://stackoverflow.com/questions/2013547/assigning-default-values-to-shell-variables-with-a-single-command-in-bash
EPUB_DIR_DEFAULT='./epub/'
EPUB_DIR=${1:-$EPUB_DIR_DEFAULT}
echo "EPUB_DIR: [$EPUB_DIR]"

# https://superuser.com/questions/644272/how-do-i-delete-all-files-smaller-than-a-certain-size-in-all-subfolders
find $EPUB_DIR -name '*.epub' -size -50k | while read small_epub; do
    echo "$small_epub seems to be too small to be valid epub."
    rm $small_epub
done
# find $EPUB_DIR -name "*.epub" -size -50k -delete