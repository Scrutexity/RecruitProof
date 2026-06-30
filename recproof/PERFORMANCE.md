# Performance

The demo highlights four performance numbers:

1. Archive size: 1,024,871 CVs
2. Parser failure count: 127
3. Duplicate count: 18,432
4. Warm FAISS lookup: 4.2ms

## Measurement note

Warm FAISS lookup is not the same as full end-to-end user latency. Production reporting should separate parse time, embedding time, index load, FAISS lookup, rerank, explanation, and export.
