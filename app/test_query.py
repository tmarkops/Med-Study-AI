from query import retrieve

results = retrieve('douleur abdominale localisation', top_k=3)
for r in results:
    print(r.node.metadata)
    print(r.node.text[:300])
    print('---')
