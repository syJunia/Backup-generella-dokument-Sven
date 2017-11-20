#!/usr/bin/python3.6
'''
Usage:
python downsample.py [offset+]amount
Examples:
cat super_big.csv | python downsample.py 1+4 > big_divided_by_4.csv
cat data.csv | python downsample.py 2 > data_halved.csv
'''

import sys
from itertools import cycle

if len(sys.argv)==1:
  print('Must specify downsample amount ([offset+]amount)', file=sys.stderr)
else:
  arg = sys.argv[1]
  if arg.find('+')!=-1:
    delay, amnt = map(int, arg.split('+'))
    for a in range(delay):
      sys.stdout.write(next(sys.stdin))
  else:
    amnt = int(arg)
  n = cycle(range(amnt))
  for l in sys.stdin:
    if next(n) == 0:
      sys.stdout.write(l)
