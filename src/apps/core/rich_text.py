"""Разбор HTML инфо-страницы на вступление, разделы (по H2) и вопросы (по H3 — для «Вопросов и ответов»).

Работает при выводе: nh3 вырезает `id` при сохранении, поэтому якоря разделов ставятся здесь. Текст уже очищен
редактором (nh3 отдаёт парные теги), так что достаточно найти границы элементов верхнего уровня.
"""

import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser

from django.utils.html import strip_tags

from apps.core.slugs import slugify_ru

# Оглавление — когда разделов столько или больше: для одного-двух оно только занимает место.
TOC_MIN_SECTIONS = 3

VOID_TAGS = {"br", "hr", "img", "col", "wbr"}


@dataclass
class Question:
    title: str  # HTML заголовка H3 без самого тега
    answer: str = ""


@dataclass
class Section:
    title: str = ""  # HTML заголовка H2 без самого тега; у вступления пусто
    anchor: str = ""
    html: str = ""  # текст раздела до первого вопроса
    questions: list[Question] = field(default_factory=list)

    @property
    def text_title(self) -> str:
        return unescape(strip_tags(self.title)).strip()

    def add(self, html: str) -> None:
        if self.questions:
            self.questions[-1].answer += html
        else:
            self.html += html


@dataclass
class InfoBody:
    intro: Section
    sections: list[Section]

    @property
    def parts(self) -> list[Section]:
        return [self.intro, *self.sections]

    @property
    def toc(self) -> list[Section]:
        return self.sections if len(self.sections) >= TOC_MIN_SECTIONS else []


class _TopLevel(HTMLParser):
    """Границы элементов верхнего уровня: [(тег, начало, конец)] — смещения в исходной строке."""

    def __init__(self, html: str):
        super().__init__(convert_charrefs=False)
        self.html = html
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", html)]
        self.blocks: list[tuple[str, int, int]] = []
        self.depth = 0
        self.start = 0
        self.feed(html)
        self.close()

    def _offset(self) -> int:
        line, column = self.getpos()
        return self.line_starts[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            if self.depth == 0:
                start = self._offset()
                self.blocks.append((tag, start, start + len(self.get_starttag_text())))
            return
        if self.depth == 0:
            self.start = self._offset()
        self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.depth == 0:
            start = self._offset()
            self.blocks.append((tag, start, start + len(self.get_starttag_text())))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS or self.depth == 0:
            return
        self.depth -= 1
        if self.depth == 0:
            end = self.html.index(">", self._offset()) + 1
            self.blocks.append((tag, self.start, end))


def _inner(html: str) -> str:
    return html[html.index(">") + 1 : html.rindex("<")]


def _wrap_tables(html: str) -> str:
    """Таблица — в обёртке с прокруткой: на телефоне широкая таблица не распирает страницу."""
    return re.sub(r"<table\b", '<div class="rich-table"><table', html).replace("</table>", "</table></div>")


def parse_info_body(html: str, *, questions: bool = False) -> InfoBody:
    """Делит текст по H2 на разделы; с `questions=True` каждый H3 — вопрос, ответ — всё до следующего заголовка."""
    html = _wrap_tables(html or "")
    intro = Section()
    sections: list[Section] = []
    current = intro
    anchors: set[str] = set()
    position = 0
    for tag, start, end in _TopLevel(html).blocks:
        current.add(html[position:start])
        block, position = html[start:end], end
        if tag == "h2":
            current = Section(title=_inner(block))
            current.anchor = _unique_anchor(current.text_title, anchors)
            sections.append(current)
        elif tag == "h3" and questions:
            current.questions.append(Question(title=_inner(block)))
        else:
            current.add(block)
    current.add(html[position:])
    for section in (intro, *sections):
        section.html = section.html.strip()
        for question in section.questions:
            question.answer = question.answer.strip()
    return InfoBody(intro=intro, sections=sections)


def _unique_anchor(title: str, taken: set[str]) -> str:
    base = slugify_ru(title, max_length=60)
    anchor, counter = base, 2
    while anchor in taken:
        anchor = f"{base}-{counter}"
        counter += 1
    taken.add(anchor)
    return anchor
