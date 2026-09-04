Bootstrap (bootstrap.min.css + bootstrap.bundle.min.js) is ALREADY bundled
here — no download needed for those. The app's layout, navbar, buttons,
tables, and the premium "Academic Ledger" theme will work immediately.

One file is still missing and needs a one-time download (only used for the
bar charts on the Analytics pages — everything else works without it):

    chart.umd.min.js
    https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js

Download command (run once, on any PC with internet, then copy this file
into this same static/vendor/ folder on the server PC):

    curl -o chart.umd.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js

Until chart.umd.min.js is added, every page works normally — only the two
bar charts under Admin > Analytics and Teacher > Analytics will not render
(the tables of numbers on those same pages still show correctly).
