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

  const SEO_FIELD_NAMES = { seo_title: "заголовок", seo_description: "описание" };

  // Что будет с текстом, если закрыть страницу, зависит от записи и полей, — об этом и говорит подсказка на время ответа.
  const pendingMessage = (isRecord, filledCount) => {
    const waiting = "Нейросеть пишет заголовок и описание — это может занять до 40 секунд.";
    if (!isRecord) return `${waiting} Не закрывайте страницу: запись ещё не сохранена, и текст появится только здесь.`;
    if (filledCount === 0) return `${waiting} Можно не ждать: если закрыть страницу, текст сохранится сам.`;
    if (filledCount === 2) return `${waiting} Дождитесь ответа: заполненные поля заменятся только после «Сохранить».`;
    return `${waiting} Пустое поле сохранится само, даже если закрыть страницу; заполненное заменится только после «Сохранить».`;
  };

  const doneMessage = (isRecord, saved) => {
    if (saved.length === 2) {
      return "Готово: текст уже на сайте. Прочитайте его, особенно цены и даты; если нужно, поправьте и сохраните.";
    }
    if (saved.length === 1) {
      const other = Object.keys(SEO_FIELD_NAMES).find((name) => name !== saved[0]);
      return `Готово: ${SEO_FIELD_NAMES[saved[0]]} уже на сайте, ${SEO_FIELD_NAMES[other]} заменится после «Сохранить». Проверьте текст.`;
    }
    return isRecord
      ? "Готово: новый текст пока только в форме. Проверьте его и нажмите «Сохранить» — иначе останется прежний."
      : "Готово: текст пока только в форме. Проверьте его и сохраните запись.";
  };

  // Кнопка «Сгенерировать» (SeoGenerateMixin): отправляет текущие значения формы и показывает ответ в полях; пустые поля
  // сохранённой записи сервер уже записал в базу. Событие input обновляет счётчики и превью.
  const setupGenerate = (titleInput) => {
    const descriptionInput = titleInput.form.elements.seo_description;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Сгенерировать";
    button.className =
      "seo-generate-button border border-base-200 cursor-pointer font-medium h-[38px] px-3 rounded-default shadow-xs shrink-0 text-sm " +
      "whitespace-nowrap hover:text-primary-600 dark:border-base-700 dark:hover:text-primary-500";
    const status = document.createElement("span");
    status.className = "text-sm";
    status.setAttribute("role", "status");
    const row = document.createElement("div");
    row.className = "flex flex-wrap items-center gap-3";
    row.style.padding = "12px 12px 0"; // как у строк полей ниже; в CSS Unfold есть не все классы Tailwind
    row.append(button, status);
    (titleInput.closest(".field-seo_title") ?? titleInput).before(row);

    const show = (message, isError = false) => {
      status.textContent = message;
      status.classList.toggle("text-red-600", isError);
      status.classList.toggle("text-base-500", !isError);
    };
    show("Нейросеть напишет заголовок и описание по тому, что сейчас в форме.");

    const seoInputs = [titleInput, descriptionInput];
    const setBusy = (busy) => {
      button.disabled = busy;
      button.textContent = busy ? "Пишем текст…" : "Сгенерировать";
      button.classList.toggle("is-generating", busy);
      seoInputs.forEach((input) => {
        input.classList.toggle("seo-generating", busy);
        input.readOnly = busy; // иначе ответ затрёт введённое; не disabled: значения должны уйти, если нажмут «Сохранить»
      });
    };

    button.addEventListener("click", async () => {
      const filledCount = seoInputs.filter((input) => input.value.trim()).length;
      if (filledCount && !confirm("Заменить заполненные SEO-поля?")) return;
      const { form } = titleInput;
      const url = titleInput.dataset.seoGenerateUrl;
      const isRecord = new URL(url, location.href).searchParams.has("object");
      const body = new FormData();
      body.append("csrfmiddlewaretoken", form.elements.csrfmiddlewaretoken.value);
      titleInput.dataset.seoSourceFields.split(",").forEach((name) => {
        body.append(name, form.elements[name]?.value ?? "");
      });
      setBusy(true);
      show(pendingMessage(isRecord, filledCount));
      try {
        const response = await fetch(url, { method: "POST", body, headers: { Accept: "application/json" } }).catch(() => {
          throw new Error("Не удалось связаться с сайтом — проверьте интернет и попробуйте ещё раз.");
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Не удалось получить текст — попробуйте ещё раз или заполните поля вручную.");
        }
        titleInput.value = data.title;
        descriptionInput.value = data.description;
        seoInputs.forEach((input) => input.dispatchEvent(new Event("input", { bubbles: true })));
        document.dispatchEvent(new CustomEvent("admin-unsaved:saved", { detail: { names: data.saved } }));
        show(doneMessage(isRecord, data.saved));
      } catch (error) {
        show(error.message, true);
      } finally {
        setBusy(false);
      }
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("input[data-seo-generate-url]").forEach(setupGenerate);
    document.querySelectorAll("input[name], textarea[name]").forEach((input) => {
      const match = input.name.match(SEO_FIELD);
      if (match) addCounter(input, LIMITS[match[2]]);
    });
    document.querySelectorAll("[data-seo-preview]").forEach(setupObjectPreview);
    document.querySelectorAll("[data-seo-site-preview]").forEach(setupSitePreview);
  });
})();
