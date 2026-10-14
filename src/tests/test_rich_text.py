from apps.core.rich_text import parse_info_body


def test_sections_split_by_h2_with_unique_anchors():
    body = parse_info_body(
        "<p>Вступление</p><h2>Общие <strong>положения</strong></h2><p>a</p>\n<ul><li><p>b</p></li></ul>"
        "<h2>Общие положения</h2><p>c</p><h2>Вещи &amp; хранение</h2>"
    )
    assert body.intro.html == "<p>Вступление</p>"
    assert [s.anchor for s in body.sections] == ["obshchie-polozheniia", "obshchie-polozheniia-2", "veshchi-khranenie"]
    first = body.sections[0]
    assert first.title == "Общие <strong>положения</strong>"
    assert first.text_title == "Общие положения"
    assert first.html == "<p>a</p>\n<ul><li><p>b</p></li></ul>"
    assert body.sections[2].text_title == "Вещи & хранение"
    assert body.sections[2].html == ""


def test_toc_only_from_three_sections():
    assert parse_info_body("<h2>Один</h2><h2>Два</h2>").toc == []
    assert len(parse_info_body("<h2>Один</h2><h2>Два</h2><h2>Три</h2>").toc) == 3


def test_nested_headings_are_not_sections():
    body = parse_info_body("<blockquote><h2>Внутри</h2><p>x</p></blockquote><p>y</p>")
    assert body.sections == []
    assert body.intro.html == "<blockquote><h2>Внутри</h2><p>x</p></blockquote><p>y</p>"


def test_questions_split_by_h3_only_when_asked():
    html = (
        "<p>Вступление</p><h3>Можно с собакой?</h3><p>Да.</p><p>На поводке.</p><h2>Оплата</h2><h3>Карта?</h3><p>Да</p>"
    )
    body = parse_info_body(html, questions=True)
    assert body.intro.html == "<p>Вступление</p>"
    assert [(q.title, q.answer) for q in body.intro.questions] == [("Можно с собакой?", "<p>Да.</p><p>На поводке.</p>")]
    assert [(q.title, q.answer) for q in body.sections[0].questions] == [("Карта?", "<p>Да</p>")]
    plain = parse_info_body(html)
    assert plain.intro.questions == []
    assert "<h3>Можно с собакой?</h3>" in plain.intro.html


def test_tables_wrapped_for_scrolling_and_void_tags_kept():
    body = parse_info_body("<p>a<br>b</p><hr><table><tbody><tr><td>1</td></tr></tbody></table>")
    assert (
        body.intro.html
        == '<p>a<br>b</p><hr><div class="rich-table"><table><tbody><tr><td>1</td></tr></tbody></table></div>'
    )


def test_empty_body():
    body = parse_info_body("")
    assert body.intro.html == "" and body.sections == []


def test_info_editor_allows_blockquote_and_table_only_there():
    from apps.core.models import InfoPage, SiteSettings

    html = '<blockquote><p>Важно</p></blockquote><table><tbody><tr><td colspan="2">1</td></tr></tbody></table>'
    assert InfoPage._meta.get_field("body").clean(html, None) == html
    cleaned = SiteSettings._meta.get_field("about_text").clean(html, None)
    assert "<blockquote>" not in cleaned and "<table>" not in cleaned
