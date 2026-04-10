from app.services.email_body_html import extract_inbound_reply_html, re_reply_subject


def test_extract_stops_at_gmail_quote() -> None:
    html = (
        '<div dir="auto">I&#39;m interested</div><br>'
        '<div class="gmail_quote gmail_quote_container"><p>Old</p></div>'
    )
    out = extract_inbound_reply_html(html)
    assert out is not None
    assert "gmail_quote" not in out
    assert "interested" in out
    assert out.startswith("<div")


def test_extract_no_quote_returns_full() -> None:
    html = "<p>Solo esto</p>"
    assert extract_inbound_reply_html(html) == "<p>Solo esto</p>"


def test_re_reply_subject() -> None:
    assert re_reply_subject("Hello there") == "Re: Hello there"
    assert re_reply_subject("Re: Already") == "Re: Already"
    assert re_reply_subject(None) is None
    assert re_reply_subject("   ") is None
