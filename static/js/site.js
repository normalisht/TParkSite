document.addEventListener("DOMContentLoaded", () => {
  const nav = (el) => ({
    nextEl: el.querySelector(".swiper-button-next"),
    prevEl: el.querySelector(".swiper-button-prev"),
  });

  document.querySelectorAll(".js-slider").forEach((el) => {
    const count = el.querySelectorAll(".swiper-slide").length;
    new Swiper(el, {
      loop: count >= 3,
      spaceBetween: 16,
      pagination: { el: el.querySelector(".swiper-pagination"), clickable: true },
      navigation: nav(el),
    });
  });

  document.querySelectorAll(".js-carousel").forEach((el) => {
    const count = el.querySelectorAll(".swiper-slide").length;
    new Swiper(el, {
      loop: count >= 6,
      spaceBetween: 24,
      slidesPerView: 1.1,
      breakpoints: { 768: { slidesPerView: 2.1 }, 1024: { slidesPerView: 3 } },
      navigation: nav(el),
    });
  });

  if (window.GLightbox && document.querySelector(".glightbox")) {
    GLightbox({ selector: ".glightbox" });
  }
});
