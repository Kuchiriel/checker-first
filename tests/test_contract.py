import checker_first as cf

def test_schema():
    assert cf.SCHEMA == "v3"

def test_verdict_shape():
    v = cf.Verdict("v3", 5, 5, True)
    d = v.to_dict()
    assert d["ok"] is True and d["ck"] == "v3" and d["passed"] == 5
