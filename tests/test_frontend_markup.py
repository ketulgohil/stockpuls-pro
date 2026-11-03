def test_upstox_tab_in_html():
    with open("static/index.html", "r") as f:
        html = f.read()
    assert "upstox-intraday" in html
    assert "Upstox Intraday Desk" in html
    assert "ws/upstox/live" in open("static/js/app.js").read()
