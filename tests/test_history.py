from syntax_viewer.history import History


def visits(*names):
    h = History()
    for n in names:
        h.visit(n)
    return h


def test_tc33_back_forward():
    h = visits("a", "b", "c")
    assert h.back() == "b"
    assert h.back() == "a"
    assert not h.can_back()
    assert h.forward() == "b"


def test_tc34_visit_truncates_forward():
    h = visits("a", "b", "c")
    h.back()
    h.visit("d")
    assert not h.can_forward()
    assert h.back() == "b"


def test_tc35_reselect_current_noop():
    assert len(visits("a", "a")) == 1


def test_tc36_clear_keeps_current():
    h = visits("a", "b", "c")
    h.back()
    h.clear()
    assert h.current == "b"
    assert not h.can_back() and not h.can_forward()


def test_reset_on_new_file():
    h = visits("a", "b")
    h.reset()
    assert h.current is None and len(h) == 0
