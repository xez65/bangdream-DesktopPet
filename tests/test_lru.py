from petcore.lru import MAX_CAPACITY, LruCache


def weigh(v):
    return len(v)


def test_evicts_oldest_first_at_capacity():
    c = LruCache(capacity=2, weigh=weigh)
    c.put("a", "1")
    c.put("b", "2")
    c.put("c", "3")
    assert c.get("a") is None
    assert c.get("b") == "2"
    assert c.get("c") == "3"


def test_hit_moves_entry_to_front():
    c = LruCache(capacity=2, weigh=weigh)
    c.put("a", "1")
    c.put("b", "2")
    c.get("a")
    c.put("c", "3")
    assert c.get("a") == "1" and c.get("b") is None


def test_pinned_entries_are_skipped_by_eviction():
    c = LruCache(capacity=2, weigh=weigh)
    c.put("a", "1")
    c.pin("a")
    c.put("b", "2")
    c.put("c", "3")
    assert c.get("a") == "1"
    assert c.get("b") is None


def test_all_pinned_cache_runs_over_capacity_instead_of_destroying():
    c = LruCache(capacity=1, weigh=weigh)
    c.put("a", "1")
    c.pin("a")
    c.put("b", "2")
    c.pin("b")
    assert len(c) == 2                      # over capacity on purpose
    c.unpin("a")
    c.put("c", "3")
    assert c.get("a") is None


def test_byte_cap_evicts_even_below_count_capacity():
    c = LruCache(capacity=100, max_bytes=10, weigh=weigh)
    c.put("a", "x" * 6)
    c.put("b", "y" * 6)
    assert c.bytes <= 10
    assert c.get("a") is None and c.get("b") == "y" * 6


def test_capacity_is_clamped():
    assert LruCache(capacity=0).capacity == 1
    assert LruCache(capacity=10_000).capacity == MAX_CAPACITY


def test_replace_existing_key_updates_bytes():
    c = LruCache(capacity=4, weigh=weigh)
    c.put("a", "xx")
    c.put("a", "xxxx")
    assert c.bytes == 4 and len(c) == 1


def test_failure_is_reported_once_per_key():
    c = LruCache(capacity=2)
    assert c.note_failure("k1") is True
    assert c.note_failure("k1") is False
    assert c.note_failure("k2") is True
    assert "failed_keys=2" in c.report()


def test_evict_key_and_report_shape():
    c = LruCache(capacity=2, weigh=weigh)
    c.put("a", "1")
    c.evict_key("a")
    assert len(c) == 0 and c.bytes == 0
    c.get("zz")
    assert c.report().startswith("size=0/2")
