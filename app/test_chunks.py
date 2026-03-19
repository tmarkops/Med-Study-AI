from query import retrieve

results = retrieve('douleur abdominale localisation', top_k=10)
print(f"Total chunks retrieved: {len(results)}\n")
for r in results:
    print(f"Page {r.node.metadata.get('page')} | score: {r.score:.4f} | chars: {len(r.node.text)}")
    print(r.node.text)
    print('=' * 60)
