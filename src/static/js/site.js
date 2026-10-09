document.addEventListener("DOMContentLoaded", () => {
  // Кнопки — внутри слайдера или рядом с ним, в обёртке .js-carousel-wrap (свои кнопки по бокам).
  const nav = (el) => {
    const root = el.closest(".js-carousel-wrap") || el;
    return {
      nextEl: root.querySelector(".js-carousel-next, .swiper-button-next"),
      prevEl: root.querySelector(".js-carousel-prev, .swiper-button-prev"),
    };
  };

  const SLIDE_DELAY = 5_000; // смена фото раз в 5 секунд
  const USER_PAUSE = 20_000; // после ручной прокрутки — пауза 20 секунд
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

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
      const lightbox = GLightbox({
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
      on: { init: showPosition, slideChange: showPosition },
    });
  });

  // Цена «700 руб / 10 выстрелов»: если единица перенеслась на вторую строку, слеш не нужен.
  // Скрываем его через visibility — ширина не меняется, поэтому перенос не «прыгает».
  const fitPrices = () => {
    document.querySelectorAll(".js-price-unit").forEach((unit) => {
      const wrapped = unit.offsetTop > unit.previousElementSibling.offsetTop;
      unit.firstElementChild.toggleAttribute("data-wrapped", wrapped);
    });
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

  if (window.GLightbox && document.querySelector(".glightbox")) {
    GLightbox({ selector: ".glightbox" });
  }
});
