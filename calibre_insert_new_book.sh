#!/usr/bin/env sh

calibredb add `find epub/ -maxdepth 1 -type f -iname '*.epub' -mtime -1 | tr '\n' ' '`
