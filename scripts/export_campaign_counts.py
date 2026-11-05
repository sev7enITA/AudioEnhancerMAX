#!/usr/bin/env python3
"""Export privately downloaded aggregate counters; QA is excluded by default."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('input', type=Path, help='counts.json downloaded from private .aemax-metrics storage')
parser.add_argument('output', type=Path)
parser.add_argument('--from-date', default='0000-00-00')
parser.add_argument('--to-date', default='9999-99-99')
parser.add_argument('--include-qa', action='store_true')
args = parser.parse_args()
data = json.loads(args.input.read_text())
if data.get('schema_version') != 1 or data.get('metric') != 'navigation_requests':
    raise SystemExit('Unsupported counter schema or metric')
totals = Counter()
with args.output.open('w', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(['day_utc','source','campaign','destination','placement','navigation_requests'])
    for day, counters in sorted(data['days'].items()):
        if not args.from_date <= day <= args.to_date:
            continue
        for key, count in sorted(counters.items()):
            source, campaign, target, placement = key.split('|')
            if not args.include_qa and (source == 'qa' or campaign.startswith('verification-')):
                continue
            if not isinstance(count, int) or count < 0:
                raise SystemExit('Invalid aggregate count')
            writer.writerow([day,source,campaign,target,placement,count])
            totals[source, target] += count
print(json.dumps({'metric':'navigation_requests','qa_included':args.include_qa,
    'totals':[{'source':s,'destination':t,'count':n} for (s,t),n in sorted(totals.items())]}, indent=2))
