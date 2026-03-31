import json, re, collections

with open('gitlab_lead_time_20260327_135209.json', encoding='utf-8') as f:
    data = json.load(f)

pattern = re.compile(r'\b([A-Z][A-Z0-9]+-\d+)\b')
mrs = data['merge_requests']['merge_requests']
total = len(mrs)
from_both = 0
from_title_only = 0
from_branch_only = 0
from_neither = 0

for mr in mrs:
    title = mr.get('title') or ''
    branch = mr.get('source_branch') or ''
    t = bool(pattern.search(title))
    b = bool(pattern.search(branch))
    if t and b:
        from_both += 1
    elif t:
        from_title_only += 1
    elif b:
        from_branch_only += 1
    else:
        from_neither += 1

print("Total MRs:", total)
print("Key in BOTH title+branch :", from_both, f"({100*from_both/total:.1f}%)")
print("Key in title only        :", from_title_only, f"({100*from_title_only/total:.1f}%)")
print("Key in branch only       :", from_branch_only, f"({100*from_branch_only/total:.1f}%)")
print("Key in NEITHER           :", from_neither, f"({100*from_neither/total:.1f}%)")
print("Total coverage (either)  :", total - from_neither, f"({100*(total-from_neither)/total:.1f}%)")

no_key = [mr for mr in mrs if not pattern.search(mr.get('title') or '') and not pattern.search(mr.get('source_branch') or '')]
print("\nSample titles without Jira key:")
for mr in no_key[:10]:
    tb = mr.get('target_branch', '')
    ti = mr.get('title', '')
    sb = mr.get('source_branch', '')
    print("  [" + tb + "] " + ti + " | branch: " + sb)
