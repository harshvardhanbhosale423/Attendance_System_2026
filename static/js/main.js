document.addEventListener("DOMContentLoaded", function () {
  // Mark All Present / Absent buttons on the bulk attendance page
  const markAllPresent = document.getElementById("markAllPresent");
  const markAllAbsent = document.getElementById("markAllAbsent");

  function setAll(value) {
    document.querySelectorAll("input[type=radio][data-role=status]").forEach(function (radio) {
      if (radio.value === value) radio.checked = true;
    });
  }

  if (markAllPresent) markAllPresent.addEventListener("click", () => setAll("present"));
  if (markAllAbsent) markAllAbsent.addEventListener("click", () => setAll("absent"));

  // auto-dismiss alerts after 6 seconds
  document.querySelectorAll(".alert").forEach(function (el) {
    setTimeout(function () {
      if (window.bootstrap) {
        const alert = window.bootstrap.Alert.getOrCreateInstance(el);
        alert.close();
      }
    }, 6000);
  });
});
