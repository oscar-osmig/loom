"""Core-engine tests: entity validation, the reverse index, transitive
inference, the O(1) BCM average, thread-local speaker state, and concurrency
safety under the live background daemon."""
import threading
import time


def test_valid_entity(loom):
    good = ["dogs", "black hole", "golden retriever", "new york"]
    bad = ["a", "the_dog", "dogs_are", "is_", "they", "will",
           "highly_intelligent", "scientist_believe", "dog.cat"]
    for g in good:
        assert loom._is_valid_entity(g), f"expected valid: {g!r}"
    for b in bad:
        assert not loom._is_valid_entity(b), f"expected invalid: {b!r}"


def test_reverse_index(loom):
    loom.add_fact("dogs", "is", "mammals")
    loom.add_fact("cats", "is", "mammals")
    loom.add_fact("mammals", "is", "animals")
    assert loom.subjects_pointing_to("mammals", "is") == {"dogs", "cats"}
    incoming = set(loom.incoming_edges("mammals"))
    assert {("dogs", "is"), ("cats", "is")} <= incoming
    # Cache invalidates on new facts.
    loom.add_fact("wolves", "is", "mammals")
    assert "wolves" in loom.subjects_pointing_to("mammals", "is")


def test_transitive_inference(loom):
    loom.add_fact("dogs", "is", "mammals")
    loom.add_fact("mammals", "is", "animals")
    loom.inference._check_chain_from("dogs", "is")
    assert "animals" in (loom.get("dogs", "is") or [])


def test_running_avg_is_bounded(loom):
    assert loom._get_recent_avg_weight() == 1.0
    for _ in range(30):
        loom.strengthen_connection("a", "is", "b", amount=0.5)
    assert 1.0 < loom._get_recent_avg_weight() <= 5.0
    assert len(loom._recent_weights) <= 20


def test_thread_local_speaker(loom):
    results = {}
    barrier = threading.Barrier(2)

    def worker(name):
        loom._session_speaker_id = name
        barrier.wait()          # both set before either reads
        time.sleep(0.02)
        results[name] = loom._session_speaker_id

    threads = [threading.Thread(target=worker, args=(n,)) for n in ("alice", "bob")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == {"alice": "alice", "bob": "bob"}


def test_concurrent_writes_with_daemon(loom):
    loom.inference.running = True
    loom.inference.start()
    errors = []

    def writer(prefix):
        try:
            for i in range(40):
                loom.add_fact(f"{prefix}{i}", "is", "thing")
                loom.get_strong_connections(1.0)
                _ = loom.knowledge
        except Exception as e:  # pragma: no cover - failure path
            errors.append(repr(e))

    threads = [threading.Thread(target=writer, args=(p,)) for p in "xyz"]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    loom.inference.stop()
    assert not errors, errors[:3]
