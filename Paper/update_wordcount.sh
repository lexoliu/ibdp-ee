#!/bin/bash

# Simple script to update word count in a single file
python3 ../count_words.py main.tex | grep "Word count:" | sed 's/Word count: \([0-9,]*\)/\1/' | tr -d ',' > wordcount.txt
echo "Word count updated in wordcount.txt"