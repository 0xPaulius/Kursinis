// Tema nustatoma prieš pirmą piešimą, kad nesimatytų baltas blyksnis.
document.documentElement.dataset.theme = localStorage.getItem("theme") === "light" ? "light" : "dark";
