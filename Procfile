# Single worker (the knowledge graph + background inference daemon live in
# process memory; multiple workers would each hold a divergent copy). Threads
# handle request concurrency; intra-process state is guarded by locks.
web: gunicorn main:app --workers 1 --threads ${GUNICORN_THREADS:-8} --timeout ${GUNICORN_TIMEOUT:-300} --bind 0.0.0.0:${PORT:-5000}
