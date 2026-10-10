// Current year in the footer (the HTML has a static fallback).
document.addEventListener("DOMContentLoaded", function () {
  const year = document.getElementById("current-year");
  if (year) {
    year.textContent = new Date().getFullYear();
  }
});
