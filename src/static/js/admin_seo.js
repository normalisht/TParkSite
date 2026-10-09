// SEO-поля в админке: счётчик символов у title/description и превью «вкладка браузера + сниппет в выдаче»
// (разметка — templates/admin/seo/_browser.html).
// - [data-seo-preview] — страница-объект: title из #id_seo_title или «Название — окончание»;
// - [data-seo-site-preview] — настройки сайта: переключатель статических страниц, данные «по умолчанию» —
//   из json_script #seo-site-pages; при вводе в поля страницы превью переключается на неё.
(() => {
  // Рекомендуемая длина: title — до 60, description — 120–160 символов.
  const LIMITS = { title: [0, 60], description: [120, 160] };
  const SEO_FIELD = /^seo_(?:(\w+)_)?(title|description)$/;
  const SERP_TITLE = 65; // примерно столько символов заголовка помещается в выдаче
  const SERP_DESCRIPTION = 165;

  const value = (selector) => document.querySelector(selector)?.value.trim() ?? "";
  const truncate = (text, max) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

  const addCounter = (input, [min, max]) => {
    const counter = document.createElement("div");
    counter.style.cssText = "font-size:12px;margin-top:4px";
    input.insertAdjacentElement("afterend", counter);
    const update = () => {
      const length = input.value.trim().length;
      const ok = length === 0 || (length >= min && length <= max);
      const hint =
        length === 0 ? "пусто — заполнится автоматически" : ok ? "хорошо" : length > max ? "длинновато" : "коротковато";
      counter.textContent = `${length} символов · рекомендуется ${min ? `${min}–` : "до "}${max} · ${hint}`;
      counter.style.color = ok ? "" : "#d97706";
    };
    input.addEventListener("input", update);
    update();
  };

  const render = (preview, { url, title, description, descriptionIsDefault }) => {
    preview.querySelector("[data-seo-preview-tab]").textContent = title;
    preview.querySelector("[data-seo-preview-url]").textContent = url;
    preview.querySelector("[data-seo-preview-title]").textContent = truncate(title, SERP_TITLE);
    const descriptionEl = preview.querySelector("[data-seo-preview-description]");
    descriptionEl.textContent = truncate(description, SERP_DESCRIPTION);
    descriptionEl.classList.toggle("is-default", descriptionIsDefault);
  };

  const setupObjectPreview = (preview) => {
    const { domain, suffix } = preview.dataset;
    const update = () => {
      const name = value("#id_name") || value("#id_title") || "Название страницы";
      const description = value("#id_seo_description");
      const slug = value("#id_slug");
      render(preview, {
        url: slug ? `${domain} › … › ${slug}` : domain,
        title: value("#id_seo_title") || `${name} — ${suffix}`,
        description: description || "Здесь будет начало текста страницы — или заполните description.",
        descriptionIsDefault: !description,
      });
    };
    document.addEventListener("input", update);
    update();
  };

  const setupSitePreview = (preview) => {
    const pages = JSON.parse(document.getElementById("seo-site-pages").textContent);
    const buttons = preview.querySelectorAll("[data-page]");
    const note = preview.querySelector("[data-seo-preview-note]");
    let current = pages[0].key;

    const update = () => {
      const page = pages.find((item) => item.key === current);
      const title = value(`#id_seo_${page.key}_title`);
      const description = value(`#id_seo_${page.key}_description`);
      render(preview, {
        url: `${preview.dataset.domain}${page.path === "/" ? "" : ` › ${page.path.replaceAll("/", "")}`}`,
        title: title || page.title,
        description: description || page.description,
        descriptionIsDefault: !description,
      });
      const empty = [!title && "title", !description && "description"].filter(Boolean);
      note.textContent = empty.length ? `Пустые поля (${empty.join(", ")}) — показан текст по умолчанию.` : "";
      buttons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.page === current)));
    };

    const select = (key) => {
      if (key && key !== current && pages.some((item) => item.key === key)) {
        current = key;
        update();
      }
    };
    buttons.forEach((button) => button.addEventListener("click", () => select(button.dataset.page)));
    // Начали править поля «Отзывы» — превью показывает отзывы.
    document.addEventListener("focusin", (event) => select(event.target.name?.match(SEO_FIELD)?.[1]));
    document.addEventListener("input", update);
    update();
  };

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("input[name], textarea[name]").forEach((input) => {
      const match = input.name.match(SEO_FIELD);
      if (match) addCounter(input, LIMITS[match[2]]);
    });
    document.querySelectorAll("[data-seo-preview]").forEach(setupObjectPreview);
    document.querySelectorAll("[data-seo-site-preview]").forEach(setupSitePreview);
  });
})();
