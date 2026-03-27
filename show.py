with open('src/unified_api.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f.readlines()[410:420], start=411):
        print(f"{i}: {line.rstrip()}")
