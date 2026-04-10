from app.services.reply_classification import classify_reply, strip_html


def test_strip_html_removes_tags() -> None:
    assert "hello" in strip_html("<p>hello</p> world").lower()
    assert "<p>" not in strip_html("<p>x</p>")


def test_classify_interested() -> None:
    assert classify_reply("I'm interested, let's talk next week") == "interested"


def test_classify_not_interested() -> None:
    assert classify_reply("Not interested, please remove me") == "not_interested"


def test_classify_later() -> None:
    assert classify_reply("Too busy right now, reach out later") == "later"


def test_classify_out_of_office() -> None:
    assert classify_reply("I no longer work at this company") == "out_of_office"


def test_classify_unknown() -> None:
    assert classify_reply("Thanks for your email") == "unknown"
