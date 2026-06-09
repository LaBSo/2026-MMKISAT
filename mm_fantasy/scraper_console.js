/**
 * MM Fantasy Player Scraper (Shadow DOM edition)
 * Paste this entire script into the browser console on the player selection page.
 * It will scroll through all pages, collect every player, and download a CSV.
 *
 * HOW TO USE:
 *   1. Open the MM Fantasy player selection page (Oma joukkue > select players view)
 *   2. Open DevTools → Console (F12 or Cmd+Option+J)
 *   3. Paste this entire script and press Enter
 *   4. Wait ~3-5 minutes while it pages through all players
 *   5. A CSV file named "mm_players.csv" will download automatically
 */

(async () => {
  const DELAY = 1500; // ms between page loads — increase if pages load slowly
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const posMap = {
    forward: "FWD",
    midfielder: "MID",
    defender: "DEF",
    goalkeeper: "GK",
  };

  const teamMap = {
    Ranska: "FRA", Englanti: "ENG", Argentiina: "ARG", Brasilia: "BRA",
    Espanja: "ESP", Portugali: "POR", Saksa: "GER",
    Italia: "ITA", Alankomaat: "NED", Belgia: "BEL", Kroatia: "CRO",
    Norja: "NOR", Senegal: "SEN", Marokko: "MAR", Algeria: "ALG",
    Kongo: "COD", "Kap Verde": "CPV", Irak: "IRQ", "Curaçao": "CUW",
    Uruguay: "URU", Meksiko: "MEX", Yhdysvallat: "USA", Kanada: "CAN",
    Japani: "JPN", "Etelä-Korea": "KOR", Australia: "AUS", Iran: "IRN",
    "Saudi-Arabia": "KSA", Qatar: "QAT", Sveitsi: "SUI", Itävalta: "AUT",
    Skotlanti: "SCO", Tšekki: "CZE", Puola: "POL", Unkari: "HUN",
    Turkki: "TUR", Romania: "ROU", Serbia: "SRB", Ukraina: "UKR",
    Slovenia: "SVN", Slovakia: "SVK", Georgia: "GEO", Albania: "ALB",
    Nigeria: "NGA", Ghana: "GHA", Kamerun: "CMR", Tunisia: "TUN",
    Egypti: "EGY", "Norsunluurannikko": "CIV", Mali: "MLI",
    Kolumbia: "COL", Ecuador: "ECU", Venezuela: "VEN", Peru: "PER",
    Chile: "CHI", Bolivia: "BOL", Paraguay: "PAR",
    Ruotsi: "SWE", "Etelä-Afrikka": "RSA", Haiti: "HAI",
    Uzbekistan: "UZB", "Bosnia ja Hertsegovina": "BIH", Jordania: "JOR",
    Panama: "PAN", "Uusi-Seelanti": "NZL",
  };

  // --- Shadow DOM helpers ---

  function getShadow(el) {
    return el && el.shadowRoot;
  }

  // Get the shadow root of the first matching custom element
  function getComponentShadow(selector) {
    const el = document.querySelector(selector);
    return el && getShadow(el);
  }

  function parsePage() {
    // The table lives inside ft-player-choice-list's shadow root
    const listEl = document.querySelector("ft-player-choice-list");
    const shadow = listEl && listEl.shadowRoot;
    if (!shadow) {
      console.warn("ft-player-choice-list shadow root not found");
      return [];
    }

    const rows = shadow.querySelectorAll("table.player-choices-table tbody tr");
    if (!rows.length) {
      console.warn("No rows found in shadow DOM table");
      return [];
    }

    const players = [];
    rows.forEach(row => {
      // ID from checkbox — in the light DOM of the row (slotted content)
      // The checkbox is in the light DOM, not shadow DOM
      const cb = row.querySelector("input[type=checkbox]");
      if (!cb) return;
      const idParts = cb.id.split("|");
      const id = idParts[idParts.length - 1];

      // Name from label in light DOM
      const nameEl = row.querySelector("label.name");
      const name = nameEl ? nameEl.textContent.trim() : "";

      // Position from ft-player-position-badge attribute
      const badge = row.querySelector("ft-player-position-badge");
      const posRaw = badge ? badge.getAttribute("position") : "";
      const position = posMap[posRaw] || posRaw;

      // Team — span.team.own is in the light DOM of the row
      const teamEl = row.querySelector("span.team.own");
      const teamName = teamEl ? teamEl.getAttribute("title") : "";
      const team = teamMap[teamName] || teamName;

      // Price
      const priceEl = row.querySelector("td.price b");
      const priceText = priceEl ? priceEl.textContent.trim() : "0";
      const price = parseFloat(priceText.replace("M", "")) || 0;

      // Points (may be "-" before tournament starts)
      const ptsEl = row.querySelector("td.totalPoints");
      const pts = ptsEl ? ptsEl.textContent.trim() : "-";
      const totalPoints = pts === "-" ? 0 : parseFloat(pts) || 0;

      // Form
      const formEl = row.querySelector("td.form");
      const form = formEl ? formEl.textContent.trim() : "-";
      const formPts = form === "-" ? 0 : parseFloat(form) || 0;

      if (name) {
        players.push({ id, name, position, team, price, totalPoints, form: formPts });
      }
    });
    return players;
  }

  function getNextButton() {
    // ft-pagination is in the light DOM; its shadow has the Next button
    const paginationEl = document.querySelector("ft-pagination");
    if (!paginationEl) return null;
    const shadow = paginationEl.shadowRoot;
    if (!shadow) return null;

    // Try aria-label "Next Page" (what the HTML shows)
    const btn = shadow.querySelector("ft-button[aria-label='Next Page']");
    if (btn) return btn;

    // Fallback: any arrow-right button that isn't disabled
    return [...shadow.querySelectorAll("ft-button.arrow-right")]
      .find(b => !b.disabled && b.getAttribute("disabled") === null);
  }

  function isNextDisabled(btn) {
    if (!btn) return true;
    // Check the ft-button element itself
    if (btn.disabled || btn.getAttribute("disabled") !== null) return true;
    if (btn.classList.contains("disabled") || btn.getAttribute("aria-disabled") === "true") return true;
    // Also check its inner button (in ft-button's shadow)
    const innerBtn = btn.shadowRoot && btn.shadowRoot.querySelector("button");
    if (innerBtn && (innerBtn.disabled || innerBtn.getAttribute("disabled") !== null)) return true;
    return false;
  }

  function clickNext(btn) {
    // Try clicking the inner <button> inside ft-button's shadow root
    const shadow = btn.shadowRoot;
    if (shadow) {
      const inner = shadow.querySelector("button");
      if (inner) { inner.click(); return; }
    }
    btn.click();
  }

  function downloadCSV(players) {
    const header = "id,name,position,team,price,totalPoints,form";
    const rows = players.map(p =>
      [p.id, `"${p.name.replace(/"/g, '""')}"`, p.position, p.team, p.price, p.totalPoints, p.form].join(",")
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "mm_players.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  // --- Main loop ---

  const allPlayers = [];
  let page = 1;

  console.log("🚀 MM Fantasy scraper started (Shadow DOM mode)...");

  // Wait for the page to fully render on first load
  await sleep(DELAY);

  while (true) {
    const players = parsePage();
    allPlayers.push(...players);
    console.log(`Page ${page}: collected ${players.length} players (total: ${allPlayers.length})`);

    if (players.length === 0) {
      console.warn("Got 0 players on this page — check if the table loaded. Retrying once...");
      await sleep(2000);
      const retry = parsePage();
      if (retry.length === 0) {
        console.error("Still 0 players. Stopping.");
        break;
      }
      allPlayers.push(...retry);
    }

    const nextBtn = getNextButton();
    if (!nextBtn || isNextDisabled(nextBtn)) {
      console.log("✅ Last page reached.");
      break;
    }

    clickNext(nextBtn);
    page++;
    await sleep(DELAY);

    // Safety cap
    if (page > 100) {
      console.warn("Hit 100-page safety cap — stopping.");
      break;
    }
  }

  // Deduplicate by id
  const seen = new Set();
  const unique = allPlayers.filter(p => {
    if (seen.has(p.id)) return false;
    seen.add(p.id);
    return true;
  });

  console.log(`\n📊 Final count: ${unique.length} unique players`);
  downloadCSV(unique);
  console.log("📥 CSV downloaded: mm_players.csv");
  console.log("Now drag that file into the MM Fantasy tool sidebar to load real player data.");
})();
