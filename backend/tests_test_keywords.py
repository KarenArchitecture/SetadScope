from app.services.keyword_matching import matched_keywords, normalize_fa

def test_persian_arabic_letters():
    assert normalize_fa("چوب آلات") == normalize_fa("چوب‌آلات")
    assert "چوب" in matched_keywords("چوب آلات")
    assert "منابع طبیعی" in matched_keywords("منابع طبيعي")

def test_not_matching_unrelated():
    assert matched_keywords("فروش ماشین آلات صنعتی") == []

def test_no_false_positive_for_barg():
    assert "برگ" not in matched_keywords("برگزاری مزایده ماشین آلات")
