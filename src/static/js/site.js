document.addEventListener("DOMContentLoaded", () => {
  // Кнопки — внутри слайдера или рядом с ним, в обёртке .js-carousel-wrap (свои кнопки по бокам).
  const nav = (el) => {
    const root = el.closest(".js-carousel-wrap") || el;
    return {
      nextEl: root.querySelector(".js-carousel-next, .swiper-button-next"),
      prevEl: root.querySelector(".js-carousel-prev, .swiper-button-prev"),
    };
  };

  const createLightbox = (options, media = "фото") => {
    const lightbox = GLightbox(options);
    // GLightbox создаёт кнопки при каждом открытии окна.
    lightbox.on("open", () => {
      lightbox.modal.querySelector(".gclose").setAttribute("aria-label", "Закрыть");
      lightbox.prevButton.setAttribute("aria-label", `Предыдущее ${media}`);
      lightbox.nextButton.setAttribute("aria-label", `Следующее ${media}`);
    });
    return lightbox;
  };

  const SLIDE_DELAY = 5_000; // смена фото раз в 5 секунд
  const USER_PAUSE = 20_000; // после ручной прокрутки — пауза 20 секунд
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Плавное раскрытие <details data-smooth>: анимируется высота обёртки [data-details-body]; без JS и при
  // «уменьшить движение» — обычный <details>. Сворачивание до конца анимации помечено атрибутом data-closing.
  document.querySelectorAll("details[data-smooth]").forEach((details) => {
    const summary = details.querySelector("summary");
    const body = details.querySelector("[data-details-body]");
    let animation = null;
    // Обрезка нужна только пока меняется высота: в покое она срезала бы обводку и тень карточек у краёв текста.
    const animate = (from, to, done) => {
      animation?.cancel();
      body.style.overflow = "hidden";
      animation = body.animate({ height: [`${from}px`, `${to}px`] }, { duration: 300, easing: "ease-out" });
      animation.onfinish = () => {
        animation = null;
        body.style.overflow = "";
        done?.();
      };
    };
    summary.addEventListener("click", (event) => {
      if (reducedMotion) return;
      event.preventDefault();
      // У закрытого <details> Chrome скрывает содержимое через content-visibility, но размер обёртки остаётся полным —
      // поэтому раскрытие из закрытого состояния начинаем с нуля, а не с измеренной высоты.
      const height = details.open ? body.getBoundingClientRect().height : 0;
      if (!details.open || details.hasAttribute("data-closing")) {
        details.removeAttribute("data-closing");
        details.open = true;
        animate(height, body.scrollHeight);
      } else {
        details.setAttribute("data-closing", "");
        animate(height, 0, () => {
          details.open = false;
          details.removeAttribute("data-closing");
        });
      }
    });
  });

  // Swiper и GLightbox подключаются только на страницах со слайдерами (partials/vendor.html).
  if (window.Swiper) document.querySelectorAll(".js-slider").forEach((el) => {
    const slides = el.querySelectorAll(".swiper-slide");
    const count = slides.length;
    const autoplay = count > 1 && !reducedMotion;
    const pagination = el.querySelector(".swiper-pagination");
    // По кругу Swiper крутит только от трёх слайдов: два фото дублируем, а точек оставляем по числу настоящих.
    const doubled = count === 2;
    if (doubled) {
      el.querySelector(".swiper-wrapper").append(...[...slides].map((slide) => slide.cloneNode(true)));
      pagination.classList.add("swiper-pagination-bullets");
      pagination.addEventListener("click", (event) => {
        const bullet = event.target.closest("[data-slide]");
        if (bullet) swiper.slideToLoop(Number(bullet.dataset.slide));
      });
    }
    const swiper = new Swiper(el, {
      loop: count >= 2,
      spaceBetween: 16,
      pagination: doubled
        ? {
            el: pagination,
            type: "custom",
            renderCustom: (s) =>
              [...Array(count).keys()]
                .map((i) => {
                  const active = i === s.realIndex % count ? " swiper-pagination-bullet-active" : "";
                  return `<span class="swiper-pagination-bullet${active}" data-slide="${i}" role="button" aria-label="Фото ${i + 1}"></span>`;
                })
                .join(""),
          }
        : { el: pagination, clickable: true },
      navigation: nav(el),
      a11y: {
        prevSlideMessage: "Предыдущее фото",
        nextSlideMessage: "Следующее фото",
        firstSlideMessage: "Это первое фото",
        lastSlideMessage: "Это последнее фото",
        paginationBulletMessage: "Перейти к фото {{index}}",
      },
      autoplay: autoplay && { delay: SLIDE_DELAY, disableOnInteraction: false },
    });

    // Пользователь листает сам: останавливаем автопрокрутку и возобновляем через 20 с после последнего его действия.
    let resumeTimer;
    const pauseByUser = () => {
      if (!autoplay) return;
      swiper.autoplay.stop();
      clearTimeout(resumeTimer);
      resumeTimer = setTimeout(() => swiper.autoplay.start(), USER_PAUSE);
    };

    // Нажатие на фото — полноэкранный просмотр. Клик после свайпа Swiper гасит сам, кнопки и точки — не слайд.
    if (window.GLightbox) {
      const lightbox = createLightbox({
        elements: [...slides].map((slide) => ({ href: slide.dataset.full, type: "image" })),
        loop: true,
      });
      let viewed = 0;
      lightbox.on("open", () => {
        clearTimeout(resumeTimer);
        if (autoplay) swiper.autoplay.stop();
      });
      lightbox.on("slide_changed", ({ current }) => {
        viewed = current.index;
      });
      lightbox.on("close", () => {
        swiper.slideToLoop(viewed, 0);
        pauseByUser();
      });
      el.addEventListener("click", (event) => {
        if (!event.target.closest(".swiper-slide")) return;
        viewed = swiper.realIndex % count;
        lightbox.openAt(viewed);
      });
    }
    if (!autoplay) return;

    swiper.on("sliderFirstMove", pauseByUser);
    swiper.on("navigationNext", pauseByUser);
    swiper.on("navigationPrev", pauseByUser);
    pagination.addEventListener("click", (event) => {
      if (event.target.closest(".swiper-pagination-bullet")) pauseByUser();
    });
  });

  if (window.Swiper) document.querySelectorAll(".js-carousel").forEach((el) => {
    const count = el.querySelectorAll(".swiper-slide").length;
    // Счётчик «3 / 12» между кнопками (на главной под отзывами, виден только на телефоне).
    const counter = el.closest(".js-carousel-wrap")?.querySelector(".js-carousel-counter");
    const showPosition = (swiper) => {
      if (counter) counter.textContent = `${swiper.realIndex + 1} / ${count}`;
    };
    new Swiper(el, {
      loop: count >= 6,
      spaceBetween: 24,
      slidesPerView: 1.1,
      breakpoints: { 768: { slidesPerView: 2.1 }, 1024: { slidesPerView: 3 } },
      navigation: nav(el),
      a11y: {
        prevSlideMessage: "Предыдущие отзывы",
        nextSlideMessage: "Следующие отзывы",
        firstSlideMessage: "Это первый отзыв",
        lastSlideMessage: "Это последний отзыв",
      },
      on: { init: showPosition, slideChange: showPosition },
    });
  });

  // Цена «1000 руб / 10 выстрелов»: если единица не влезла в строку, слеш убираем, а единицу ставим блоком с новой строки.
  // Сначала снимаем отметку у всех цен, потом меряем все разом — одна перекомпоновка, и сужение/расширение окна работает в обе стороны.
  const fitPrices = () => {
    const units = [...document.querySelectorAll(".js-price-unit")];
    units.forEach((unit) => unit.removeAttribute("data-wrapped"));
    const wrapped = units.map((unit) => unit.offsetTop > unit.previousElementSibling.offsetTop);
    units.forEach((unit, i) => unit.toggleAttribute("data-wrapped", wrapped[i]));
  };
  let fitFrame;
  const scheduleFit = () => {
    cancelAnimationFrame(fitFrame);
    fitFrame = requestAnimationFrame(fitPrices);
  };
  fitPrices();
  window.addEventListener("resize", scheduleFit);
  document.fonts?.ready.then(scheduleFit);

  // «Кирпичная» раскладка отзывов: карточки по очереди раскладываются по колонкам (1-я — в первую, 2-я — во вторую…),
  // поэтому высота у каждой своя, без пустот, а порядок «от новых к старым» читается слева направо.
  const columnQueries = [window.matchMedia("(min-width: 64rem)"), window.matchMedia("(min-width: 40rem)")];
  const columnCount = () => (columnQueries[0].matches ? 3 : columnQueries[1].matches ? 2 : 1);
  document.querySelectorAll(".js-masonry").forEach((grid) => {
    const items = Array.from(grid.children);
    let current = 0;
    const layout = () => {
      const count = columnCount();
      if (count === current) return;
      current = count;
      if (count === 1) {
        grid.replaceChildren(...items);
        return;
      }
      const columns = Array.from({ length: count }, () => {
        const column = document.createElement("div");
        column.className = "flex min-w-0 flex-col gap-6";
        return column;
      });
      items.forEach((item, index) => columns[index % count].append(item));
      grid.replaceChildren(...columns);
    };
    layout();
    columnQueries.forEach((query) => query.addEventListener("change", layout));
  });

  const VIDEO_LINK = '.glightbox[data-type="external"]';
  const PHOTO_LINK = `.glightbox:not(${VIDEO_LINK})`;
  if (window.GLightbox && document.querySelector(PHOTO_LINK)) {
    createLightbox({ selector: PHOTO_LINK, loop: true });
  }

  // Ролики Дзена (content/partials/video_card.html): слайд — пустая рамка, iframe создаём сами и только у открытого слайда.
  // Слайд external не годится: GLightbox ставит iframe лишь src (allow после загрузки не действует, нужна перезагрузка)
  // и заранее грузит соседние слайды; iframe ушедшего слайда остался бы играть за кадром — его убираем.
  const videoGalleries = new Map();
  document.querySelectorAll(VIDEO_LINK).forEach((link) => {
    const name = link.dataset.gallery;
    videoGalleries.set(name, [...(videoGalleries.get(name) || []), link]);
  });
  // Кавычки тоже: результат попадает и в значение атрибута.
  const escapeHtml = (text) => {
    const span = document.createElement("span");
    span.textContent = text;
    return span.innerHTML.replaceAll('"', "&quot;");
  };
  // «Открыть на Дзене» под плеером — только у ролика с адресом на Дзене (data-dzen-* карточки). Адрес проверяем и здесь:
  // перенос канала Дзена (dzen_import.py) пишет его в базу без full_clean().
  const DZEN_PAGE = /^https:\/\/dzen\.ru\//;
  const dzenLink = ({ dzenUrl, dzenLabel }) =>
    DZEN_PAGE.test(dzenUrl || "")
      ? `<a class="video-dzen-link" href="${escapeHtml(dzenUrl)}" target="_blank" rel="noopener">${escapeHtml(dzenLabel || "")}</a>`
      : "";
  if (window.GLightbox) videoGalleries.forEach((links) => {
    const lightbox = createLightbox({
      elements: links.map((link) => ({
        type: "inline",
        content: '<div class="video-frame"></div>',
        title: escapeHtml(link.dataset.title || ""), // подпись GLightbox вставляет как HTML, а название приходит с Дзена
        description: dzenLink(link.dataset),
        width: "auto",
        height: "auto",
      })),
      loop: true,
      moreLength: 0, // иначе на телефоне GLightbox обрезает описание и прячет ссылку за «See more»
    }, "видео");
    // При закрытии GLightbox удаляет окно вместе с iframe, остаётся перелистывание. Уходящий ролик убираем в начале
    // анимации, иначе его звук идёт ещё ~0,5 с; slide_changed ниже дочищает остальное при быстром листании.
    lightbox.on("slide_before_change", ({ prev }) => {
      prev.slideNode?.querySelectorAll(".video-frame iframe").forEach((iframe) => iframe.remove());
    });
    // Слайд берём у окна, а не из события: при открытии в событии его ещё нет, а при быстром листании он уже другой.
    lightbox.on("slide_changed", () => {
      const slide = lightbox.getActiveSlide();
      lightbox.slidesContainer.querySelectorAll(".video-frame iframe").forEach((iframe) => {
        if (!slide.contains(iframe)) iframe.remove();
      });
      const frame = slide.querySelector(".video-frame");
      if (!frame || frame.querySelector("iframe")) return;
      const link = links[lightbox.index];
      const iframe = document.createElement("iframe");
      iframe.allow = "autoplay; fullscreen; picture-in-picture; encrypted-media";
      iframe.allowFullscreen = true;
      iframe.title = link.dataset.title || "";
      iframe.src = link.href;
      frame.append(iframe);
    });
    links.forEach((link, index) =>
      link.addEventListener("click", (event) => {
        event.preventDefault();
        lightbox.openAt(index);
      }),
    );
  });
});
