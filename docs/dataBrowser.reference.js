const MAX_PANELS = 9;          // absolute number of panel slots
const MOBILE_MAX_PANELS = 2;   // narrow-screen cap
let maxPanels = MAX_PANELS;    // live cap (lowered on narrow screens)

const GRANULARITY_ORDER = ['daily', 'monthly', 'seasonal', 'yearly'];

// Meteorological seasons: MAM (spring, starts March), JJA (summer, starts June),
// SON (autumn, starts September), DJF (winter, starts December). Maps a month
// (1-12) to [seasonStartMonth, yearOffset] -- yearOffset is -1 for Jan/Feb, since
// they belong to the winter that started the previous December.
const SEASON_START_BY_MONTH = {
    1: [12, -1], 2: [12, -1], 3: [3, 0], 4: [3, 0], 5: [3, 0],
    6: [6, 0], 7: [6, 0], 8: [6, 0], 9: [9, 0], 10: [9, 0], 11: [9, 0], 12: [12, 0],
};

// The YYYYMM of the meteorological season a date falls in, regardless of which
// month within that season the date itself is (e.g. April and May both resolve
// to March of the same year, the season's start month).
function seasonStartYYYYMM(ymd) {
    const year = parseInt(ymd.slice(0, 4), 10);
    const month = parseInt(ymd.slice(4, 6), 10);
    const [startMonth, yearOffset] = SEASON_START_BY_MONTH[month];
    return String(year + yearOffset) + String(startMonth).padStart(2, '0');
}

// ymd is the existing YYYYMMDD string (from datePicker.valueAsDate); trim it to
// match what each granularity's endpoint expects.
function granularityDateString(ymd, granularity) {
    if (granularity === 'yearly') return ymd.slice(0, 4);
    if (granularity === 'daily') return ymd;
    if (granularity === 'seasonal') return seasonStartYYYYMM(ymd);
    return ymd.slice(0, 6); // monthly
}

function plotImageUrl(plotId, granularity, ymd) {
    return '$APIURL/visualizations/byID/' + plotId + '/' + granularity + '/' + granularityDateString(ymd, granularity);
}

// Radiosonde-style plots (see the `multi` flag from /visualizations/byInstrument)
// can have more than one image on a single day, e.g. one per launch. Only the
// `daily` granularity supports this -- the items endpoints hardcode it.
function plotItemsCountUrl(plotId, ymd) {
    return '$APIURL/visualizations/byID/' + plotId + '/daily/' + ymd + '/items';
}
function plotItemUrl(plotId, ymd, i) {
    return '$APIURL/visualizations/byID/' + plotId + '/daily/' + ymd + '/items/' + i;
}
async function fetchItemCount(plotId, ymd) {
    const res = await fetch(plotItemsCountUrl(plotId, ymd));
    if (!res.ok) throw new Error('Failed to load item count for ' + plotId);
    const data = await res.json();
    return data.count || 0;
}

// Panels are identified by their numeric index (0-based); these helpers map an
// index to its DOM element / sub-elements / URL param so the rest of the code
// never has to parse ids out of strings.
const panelEl     = (i) => document.getElementById('panel-' + i);
const panelImg    = (i) => panelEl(i).querySelector('img');
const panelHeader = (i) => panelEl(i).querySelector('.breadcrumb');
const panelCredit = (i) => panelEl(i).querySelector('.panel-credit');
const panelParam  = (i) => 'p' + (i + 1);   // URL param name (1-based, back-compat)

// Every plot shown here is published under CC BY 4.0, which requires the
// attribution and a link to the licence to travel with the image itself -- so it
// is rendered under each panel plot and under the click-to-enlarge view, not just
// once in the Impressum.
const CC_BY_URL = 'https://creativecommons.org/licenses/by/4.0/';
const IMAGE_CREDIT_HTML =
      '© Universität zu Köln, IGMK · '
    + '<a href="' + CC_BY_URL + '" target="_blank" rel="license noopener">CC BY 4.0</a>';

// The credit only applies to an actual plot, so it is hidden while the panel is
// still showing the placeholder graphic (empty panel, or a day without data).
function updatePanelCredit(i) {
    const credit = panelCredit(i);
    if (!credit) return;
    credit.style.display = panelImg(i).src.includes('placeholder') ? 'none' : 'block';
}

const recalcThumbnailsEvent = new CustomEvent('recalcThumbnails',{ detail: { yourData: 'Here is some data' } });
var openPlots = Array(MAX_PANELS).fill().map(() => Array(3).fill(''));
var panelPlotMeta = Array(MAX_PANELS).fill(null); // {plotId, granularities, current, multi, itemCount, itemIndex} | null
var selectedPanel;

let url = new URL(window.location.href);
let params = url.searchParams;
let selectedDate = params.get('date');
if (selectedDate === '0') {
    selectedDate = new Date().toISOString().split('T')[0];
} else if (selectedDate === '-1') {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    selectedDate = yesterday.toISOString().split('T')[0];
}
let menu_state = params.get('ms') ? params.get('ms').split(',') : ['',''];

// Indices of the panels currently on screen, in display order.
let currentOpenPanels = [];
for (let i = 0; i < MAX_PANELS; i++) {
    if (params.get(panelParam(i)) != null) currentOpenPanels.push(i);
}
if (!currentOpenPanels.length) {
    currentOpenPanels.push(0);
}

// Push the current params to the address bar as a new history entry.
function pushUrl() {
    window.history.pushState({}, '', `${window.location.pathname}?${params.toString()}`);
}

function updateMenuUrl() {
    params.set('ms', menu_state.join(','));
    pushUrl();
}

// Create the (initially hidden) panel elements once. Keeping them in JS avoids
// duplicating identical markup per panel and makes MAX_PANELS the single knob.
function buildPanels() {
    const wrapper = document.getElementById('plotsWrapper');
    for (let i = 0; i < MAX_PANELS; i++) {
        const panel = document.createElement('div');
        panel.className = 'panel';
        panel.id = 'panel-' + i;
        panel.style.display = 'none';
        panel.innerHTML =
            `<div class="panel-controls">`
          + `<nav class="breadcrumb" aria-label="breadcrumb"></nav>`
          + `<button type="button" class="panel-close" onclick="closePanel(${i})" aria-label="Close panel">&times;</button>`
          + `</div>`
          + `<nav class="granularity-switcher" style="display:none"></nav>`
          + `<nav class="granularity-switcher item-switcher" style="display:none"></nav>`
          + `<img src="./img/placeholder.svg">`
          + `<div class="panel-credit" style="display:none">${IMAGE_CREDIT_HTML}</div>`;
        wrapper.appendChild(panel);
    }
}

document.addEventListener("DOMContentLoaded", function() {
    buildPanels();
    var dateInput = document.getElementById('datePicker');
    // Prevent picking a future date via the calendar widget.
    dateInput.max = new Date().toISOString().split('T')[0];
    dateInput.addEventListener('change', commitDate);
    applyStateFromUrl();
    initPanelZoom();
});

// Click-to-enlarge: clicking a panel plot shows it full-screen as an overlay;
// clicking the overlay (or pressing Esc) returns to the normal view.
function initPanelZoom() {
    const overlay = document.createElement('div');
    overlay.id = 'panelZoom';
    const figure = document.createElement('figure');
    const big = document.createElement('img');
    const credit = document.createElement('figcaption');
    credit.className = 'zoom-credit';
    credit.innerHTML = IMAGE_CREDIT_HTML;
    // The overlay closes on any click, so the licence link needs to survive its own.
    credit.addEventListener('click', (e) => e.stopPropagation());
    figure.appendChild(big);
    figure.appendChild(credit);
    overlay.appendChild(figure);
    document.body.appendChild(overlay);

    const closeZoom = () => overlay.classList.remove('open');
    overlay.addEventListener('click', closeZoom);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeZoom();
    });

    document.querySelectorAll('.panel img').forEach((img) => {
        img.addEventListener('click', () => {
            if (img.src.includes('placeholder')) return;
            big.src = img.src;
            overlay.classList.add('open');
        });
    });
}

// Re-render the page whenever the URL changes via the browser's back/forward
// buttons. Without this, pushState() updates the address bar but the content
// stays stale until a full reload (F5).
window.addEventListener('popstate', function() {
    applyStateFromUrl();
});

// Read the current URL and rebuild the page state to match. Used both on the
// initial load and on every popstate (back/forward) navigation.
function applyStateFromUrl() {
    url = new URL(window.location.href);
    params = url.searchParams;

    // ---- date ----
    selectedDate = params.get('date');
    if (selectedDate === '0') {
        selectedDate = new Date().toISOString().split('T')[0];
    } else if (selectedDate === '-1') {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        selectedDate = yesterday.toISOString().split('T')[0];
    } else if (selectedDate === null) {
        selectedDate = new Date().toISOString().split('T')[0];
    }
    document.getElementById('datePicker').value = selectedDate;

    // ---- panels / plots ----
    const panelInfos = Array.from({ length: MAX_PANELS }, (_, i) => params.get(panelParam(i)));
    menu_state = params.get('ms') ? params.get('ms').split(',') : ['', ''];

    currentOpenPanels = panelInfos.flatMap((info, i) => info != null ? [i] : []);
    if (!currentOpenPanels.length) {
        currentOpenPanels.push(0);
    }

    openPlots = Array(MAX_PANELS).fill().map(() => Array(3).fill(''));

    setPanelNumber();
    updatePanelPositions();

    // Reset every panel to a blank slate before re-applying the URL state, so
    // that panels closed in the target state don't keep showing stale plots.
    for (let i = 0; i < MAX_PANELS; i++) {
        panelImg(i).src = './img/placeholder.svg';
        updatePanelCredit(i);
        panelPlotMeta[i] = null;
        renderGranularitySwitcher(i);
        renderItemSwitcher(i);
        renderBreadcrumb(i); // empty tree -> just the "Sites" root
    }

    panelInfos.forEach((info, i) => {
        if (!info) return;
        const fields = info.split(',');
        openPlots[i] = fields.slice(0, 3);       // site, instrument, plotId
        restorePanelPlot(i, fields[3] || null);  // fields[3]: linked granularity, if any
    });

    // ---- view selection ----
    const hasUrlParams = panelInfos.some((info) => info != null) || menu_state[0] !== '';
    if (menu_state[0] !== '') {
        openPlots[0] = [...menu_state, ''];
        changePlot(0);
    } else if (!hasUrlParams) {
        showMap();
    } else {
        document.getElementById('selectionMenu').style.display = 'none';
        document.getElementById('mapFrame').style.display = 'none';
        document.getElementById('plotsWrapper').style.display = 'grid';
        exitMenuMode();
    }
}

document.addEventListener('keydown', function(event) {
  if (document.activeElement.id !== 'searchBar'){
    if (event.key === 'a' || event.key === 'ArrowLeft') {
        updateDate(-1);
    } else if (event.key === 's'|| event.key === 'ArrowRight'){
        updateDate(1);
    } else if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
        // Page through open multi-item (radiosonde-style) panels' items, same way
        // ArrowLeft/Right page every open panel's date. Only prevent the page's
        // default scroll if something was actually there to step through.
        if (stepItem(event.key === 'ArrowDown' ? 1 : -1)) event.preventDefault();
    }
  }
});

window.addEventListener("resize", function() {
    setPanelNumber();
    updatePanelPositions();
});

function setPanelNumber() {
    maxPanels = window.innerWidth < 600 ? MOBILE_MAX_PANELS : MAX_PANELS;
    if (currentOpenPanels.length > maxPanels) {
        currentOpenPanels.splice(maxPanels);
    }
};

function newPanel() {
    if (currentOpenPanels.length >= maxPanels) return;
    for (let i = 0; i < MAX_PANELS; i++) {
        if (!currentOpenPanels.includes(i)) {
            currentOpenPanels.push(i);
            updatePanelPositions();
            renderBreadcrumb(i); // show the "Sites" entry point on the new empty panel
            return;
        }
    }
};

function closePanel(i) {
    const index = currentOpenPanels.indexOf(i);
    if (index > -1) {
        currentOpenPanels.splice(index, 1);
    }
    // Forget the panel's plot and drop its URL param so it stays closed on reload.
    openPlots[i] = ['', '', ''];
    panelPlotMeta[i] = null;
    renderGranularitySwitcher(i);
    renderItemSwitcher(i);
    params.delete(panelParam(i));
    pushUrl();
    updatePanelPositions();
};

async function changePlot(i) {
    selectedPanel = i;
    var currentPlotTree = openPlots[i];
    document.getElementById("selectionMenu").style.display = "grid";
    document.getElementById("searchBar").classList.add("open");
    document.getElementById("plotsWrapper").style.display = "none";
    enterMenuMode();
    if (currentPlotTree[1] !=''){
        getPlots(currentPlotTree[1], i)
    } else if (currentPlotTree[0] !='') {
        getInstruments(currentPlotTree[0], i)
    } else {
        try {
            const response = await fetch('$APIURL/sites');
            const data = await response.json();
            populateGrid(data,"sites",i);
        }
        catch (error) {
            alert('Error: ' + error.message); // display an error message in an alert
        }
    }
};

function populateGrid(data,state,panel) {
    const grid = document.getElementById('selectionMenu');
    grid.innerHTML = '';
    grid.dataset.state = state;
    const crumbBar = document.createElement('nav');
    crumbBar.id = 'menuBreadcrumb';
    crumbBar.className = 'menu-breadcrumb';
    crumbBar.setAttribute('aria-label', 'breadcrumb');
    grid.appendChild(crumbBar);   // reserve first slot synchronously
    renderMenuBreadcrumb(panel);  // fills crumbBar async; not awaited
    if (state === 'plots') {
        renderPlotTiles(data, panel, grid);
    } else {
        Object.entries(data).forEach(([key, value]) => {
            grid.appendChild(createTile(key, value, state, panel));
        });
    }
    updateBackButton(state);
};

// data: [{id, granularities}] from /visualizations/byInstrument/{id}. If every plot
// has a single granularity, they render as a flat, header-less grid (unchanged from
// before). As soon as at least one plot has more than one granularity, plots are
// grouped into one section per granularity (styled like the search-results category
// headers, and click-to-collapse): each section lists that granularity's tile for
// every plot supporting it, so picking a tile also picks the granularity to open.
// Single-granularity plots are folded into the "daily" section alongside the
// multi-granularity ones rather than sitting in a separate flat area next to it.
// Only the "daily" section starts expanded; the rest start collapsed and don't load
// their thumbnails (no request is made) until the user expands them.
function renderPlotTiles(data, panel, grid) {
    const single = data.filter(p => !p.granularities || p.granularities.length <= 1);
    const multi = data.filter(p => p.granularities && p.granularities.length > 1);

    if (!multi.length) {
        single.forEach((plot, i) => grid.appendChild(createTile(String(i), plot, 'plots', panel)));
        return;
    }

    GRANULARITY_ORDER.forEach(gran => {
        const plots = gran === 'daily'
            ? single.concat(multi.filter(p => p.granularities.includes(gran)))
            : multi.filter(p => p.granularities.includes(gran));
        if (!plots.length) return;
        const expanded = gran === 'daily';

        const header = document.createElement('h3');
        header.className = 'search-section section-toggle' + (expanded ? ' expanded' : '');
        header.textContent = gran;

        const body = document.createElement('div');
        body.className = 'section-body';
        body.style.display = expanded ? 'contents' : 'none';

        const tiles = plots.map((plot, i) => createTile(String(i), plot, 'plots', panel, false, gran, !expanded));
        tiles.forEach(t => body.appendChild(t));

        let loaded = expanded;
        header.addEventListener('click', () => {
            const nowExpanded = body.style.display === 'none';
            body.style.display = nowExpanded ? 'contents' : 'none';
            header.classList.toggle('expanded', nowExpanded);
            if (nowExpanded && !loaded) {
                loaded = true;
                tiles.forEach(t => t.loadThumbnail && t.loadThumbnail());
            }
        });

        grid.appendChild(header);
        grid.appendChild(body);
    });
}

// Open `plotId` (at `gran`, with its known `granularities`/`multi`-ness) into `panel`,
// switching from the picker back to the plots view. Shared by createTile's plain
// single-thumbnail click handler and the multi-item click handlers below, which only
// differ in which `itemIndex` they want to open.
function openPlotInPanel(panel, fromSearch, plotId, gran, granularities, multi, itemIndex) {
    // from search there is no site/instrument context: breadcrumb is "Sites > plot"
    openPlots[panel] = fromSearch ? ['', '', plotId] : [openPlots[panel][0], openPlots[panel][1], plotId];
    params.delete('ms');
    // populateTile sets the pN param and pushes a single history entry
    populateTile(plotId, panel, true, gran, granularities, multi, itemIndex);
    document.getElementById("selectionMenu").style.display = "none";
    document.getElementById("plotsWrapper").style.display = "grid";
    exitMenuMode();
}

// Build one tile for a single item of a multi-item (radiosonde-style) plot -- same
// look as a normal plot tile, labeled with its 1-based item number since every item
// shares the same plotId. Used by createTile's multi+daily branch, which renders
// one of these per item instead of a single tile with several thumbnails nested
// inside.
function buildItemTile(plotId, ymd, idx, panel, fromSearch, gran, granularities, multi) {
    const tile = document.createElement('div');
    tile.className = 'tile';

    const valueEl = document.createElement('div');
    valueEl.className = 'tile-value';
    valueEl.textContent = plotId + ' #' + (idx + 1);

    const img = document.createElement('img');
    img.className = 'tile-img';
    img.src = plotItemUrl(plotId, ymd, idx);

    tile.appendChild(valueEl);
    tile.appendChild(img);

    tile.addEventListener('click', () => openPlotInPanel(panel, fromSearch, plotId, gran, granularities, multi, idx));

    return tile;
}

// Build a single selection-menu tile. Shared by populateGrid (sites/instruments/plots
// navigation) and searchItems (search results). `state` drives the click behaviour:
//   sites       -> value is the display name; opens that site's instruments
//   instruments -> value is {description} (navigation) or a plain string (search); opens its plots
//   plots       -> value is {id, granularities, multi} (navigation) or a plain plot-id
//                  string (search); opens the plot in `panel`
// `fromSearch` marks a search result, which carries no parent context: selecting it
// clears the unknown levels instead of inheriting whatever was previously in the tree.
// `granularity` (plots state only) is the granularity this tile represents, when it
// was rendered inside one of renderPlotTiles' per-granularity sections. `lazy` defers
// the thumbnail request until `tile.loadThumbnail()` is called (used for sections that
// start collapsed, so they don't fetch anything until expanded).
function createTile(key, value, state, panel, fromSearch=false, granularity=null, lazy=false) {
    const tile = document.createElement('div');
    tile.className = 'tile';

    const valueEl = document.createElement('div');
    valueEl.className = 'tile-value';
    valueEl.textContent = value;          // the visible text

    const keyEl = document.createElement('div');
    keyEl.className = 'tile-key';
    keyEl.textContent = key;              // optional – shows the key too

    const img = document.createElement('img');
    img.className = 'tile-img';
    img.src = 'img/thumbnails/'+key+'.jpg';

    tile.appendChild(valueEl);
    tile.appendChild(keyEl);
    tile.appendChild(img);

    if (state==="sites") {
        tile.addEventListener('click', () => {
            openPlots[panel] = [key, '', ''];
            menu_state = openPlots[panel].slice(0,-1);
            updateMenuUrl();
            getInstruments(key,panel);
        });
    } else if (state==="instruments"){
        // navigation passes {description, ...}; search passes a plain display string
        valueEl.textContent = (value && value.description) ? value.description : value;
        tile.addEventListener('click', () => {
            // from search there is no known site context, so clear it
            openPlots[panel] = [fromSearch ? '' : openPlots[panel][0], key, ''];
            menu_state = openPlots[panel].slice(0,-1);
            updateMenuUrl();
            getPlots(key,panel);
        });
    } else if (state==="plots"){
        // navigation passes {id, granularities, multi}; search still passes a plain plot-id string
        const plotId = (value && typeof value === 'object') ? value.id : value;
        const granularities = (value && typeof value === 'object' && value.granularities && value.granularities.length)
            ? value.granularities : ['daily'];
        const multi = !!(value && typeof value === 'object' && value.multi);
        const gran = granularity || granularities[0];

        if (multi && gran === 'daily') {
            // Radiosonde-style plot: can have more than one image (e.g. launch) on this
            // day. Render each item as its own separate tile rather than nesting several
            // thumbnails inside one -- grouped under a display:contents wrapper (same
            // trick renderPlotTiles' collapsible sections use) so each item lays out as
            // its own grid cell alongside the regular tiles.
            const group = document.createElement('div');
            group.className = 'tile-items-group';
            group.style.display = 'contents';

            const loadItems = async () => {
                const ymd = document.getElementById("datePicker").valueAsDate.toISOString().slice(0, 10).replace(/-/g, '');
                group.innerHTML = '';
                try {
                    const count = await fetchItemCount(plotId, ymd);
                    for (let idx = 0; idx < count; idx++) {
                        group.appendChild(buildItemTile(plotId, ymd, idx, panel, fromSearch, gran, granularities, multi));
                    }
                } catch (error) {
                    // leave the group empty -- nothing to show for this day
                }
            };
            if (lazy) {
                group.loadThumbnail = () => {
                    loadItems();
                    group.addEventListener('recalcThumbnails', loadItems);
                    group.loadThumbnail = null;
                };
            } else {
                loadItems();
                group.addEventListener('recalcThumbnails', loadItems);
            }
            return group;
        }

        valueEl.textContent = plotId;
        const setThumb = () => {
            const ymd = document.getElementById("datePicker").valueAsDate.toISOString().slice(0, 10).replace(/-/g, '');
            img.src = plotImageUrl(plotId, gran, ymd);
            tile.style.display = "block";
            img.onerror = function() {
                tile.style.display = "none";
            };
        };
        if (lazy) {
            // Collapsed section: don't fetch anything until the section is expanded
            // (renderPlotTiles calls this), and only start tracking date changes once
            // it has actually been loaded.
            tile.loadThumbnail = () => {
                setThumb();
                img.addEventListener('recalcThumbnails', setThumb);
                tile.loadThumbnail = null;
            };
        } else {
            setThumb();
            img.addEventListener('recalcThumbnails', setThumb);
        }

        tile.addEventListener('click', () => openPlotInPanel(panel, fromSearch, plotId, gran, granularities, multi, 0));
    } else {alert("unknown state")}

    return tile;
};

// Split a breadcrumb site field into its individual site ids. Accepts '+' as the
// multi-site delimiter; also tolerates spaces, since URLSearchParams decodes a
// literal '+' in the query string to a space.
function siteIds(siteField) {
    return (siteField || '').split(/[+\s]+/).filter(Boolean);
}

async function getInstruments(siteId,panel) {
    try {
        // siteId may be a '+'-joined list of sites (e.g. a linked multi-site state);
        // fetch each site's instruments and merge them into one grid.
        const ids = siteIds(siteId);
        const results = await Promise.all(
            ids.map(id => fetch('$APIURL/sites/'+id+'/instruments').then(r => r.json()))
        );
        const data = Object.assign({}, ...results); // merge; dup ids: last wins
        populateGrid(data,"instruments",panel);
    } catch (error) {
        alert('Error: ' + error.message); // display an error message in an alert
    }
};
async function getPlots(instrumentId,panel){
    try {
        const response = await fetch('$APIURL/visualizations/byInstrument/'+instrumentId);
        const data = await response.json();
        populateGrid(data,"plots",panel);
    } catch (error) {
        alert('Error: ' + error.message); // display an error message in an alert
    }
};
// ---- Breadcrumb label resolution: map site/instrument ids to their display
// names via the API, cached (and request-deduped) so date changes and multiple
// panels don't refetch. Falls back to the id if a name can't be resolved. ----
let sitesMetaPromise;
function fetchSitesMeta() {
    if (!sitesMetaPromise) {
        sitesMetaPromise = fetch('$APIURL/sites').then(r => r.json()).catch(() => ({}));
    }
    return sitesMetaPromise;
}
const instMetaPromises = {};
function fetchInstrumentsMeta(siteId) {
    if (!instMetaPromises[siteId]) {
        instMetaPromises[siteId] = fetch('$APIURL/sites/' + siteId + '/instruments').then(r => r.json()).catch(() => ({}));
    }
    return instMetaPromises[siteId];
}
async function siteLabel(siteId) {
    if (!siteId) return '';
    const sites = await fetchSitesMeta();
    // For a multi-site field, resolve each id and join the display names.
    return siteIds(siteId).map(id => sites[id] || id).join(' + ');
}
async function instrumentLabel(siteId, instId) {
    if (!instId) return '';
    if (!siteId) return instId;
    // The instrument may belong to any of the listed sites; search each in turn.
    for (const id of siteIds(siteId)) {
        const insts = await fetchInstrumentsMeta(id);
        const entry = insts[instId];
        if (entry) return entry.description || instId;
    }
    return instId;
}

// Cached (and request-deduped) per-instrument plot list, used to recover a plot's
// available granularities when a panel is restored from the URL (the URL only
// stores the plot id, not its granularities).
const instPlotsPromises = {};
function fetchInstrumentPlots(instrumentId) {
    if (!instPlotsPromises[instrumentId]) {
        instPlotsPromises[instrumentId] = fetch('$APIURL/visualizations/byInstrument/' + instrumentId).then(r => r.json()).catch(() => []);
    }
    return instPlotsPromises[instrumentId];
}

// Reopen a panel's plot from a parsed URL tree (openPlots[i] already set). Looks up
// the plot's granularities via its instrument, if known, so the switcher still shows
// on a direct link / page reload; `urlGranularity` (the link's 4th field, if present)
// picks which one to open at.
async function restorePanelPlot(i, urlGranularity) {
    const [, instrumentId, plotId] = openPlots[i];
    let granularities = null;
    let multi = false;
    if (instrumentId) {
        const plots = await fetchInstrumentPlots(instrumentId);
        const match = Array.isArray(plots) ? plots.find(p => p.id === plotId) : null;
        if (match) {
            if (match.granularities && match.granularities.length) granularities = match.granularities;
            multi = !!match.multi;
        }
    }
    populateTile(plotId, i, false, urlGranularity, granularities, multi);
}

// The pN URL value for a panel: site,instrument,plotId, plus a 4th "current granularity"
// field so a specific granularity is linkable -- but only when the plot actually has more
// than one, so single-granularity (the vast majority) links stay exactly as before.
function panelUrlValue(i) {
    const meta = panelPlotMeta[i];
    return (meta && meta.granularities.length > 1) ? [...openPlots[i], meta.current] : openPlots[i];
}

// Load panel `i`'s image for its current plotId/granularity/date. For a `multi`
// plot viewed at `daily` granularity, this fetches how many items exist for the
// day and shows `itemIndex` (clamped to the count); otherwise it's the plain
// single-image byID URL, unchanged. Always (re)renders the item switcher, since
// itemCount may have just changed.
async function loadPanelImage(i, itemIndex) {
    const meta = panelPlotMeta[i];
    const ymd = document.getElementById("datePicker").valueAsDate.toISOString().slice(0, 10).replace(/-/g, '');
    if (meta.multi && meta.current === 'daily') {
        const count = await fetchItemCount(meta.plotId, ymd).catch(() => 0);
        meta.itemCount = count;
        meta.itemIndex = count ? Math.min(itemIndex, count - 1) : 0;
        panelImg(i).src = count ? plotItemUrl(meta.plotId, ymd, meta.itemIndex) : './img/placeholder.svg';
    } else {
        meta.itemCount = 0;
        panelImg(i).src = plotImageUrl(meta.plotId, meta.current, ymd);
    }
    updatePanelCredit(i);
    renderItemSwitcher(i);
}

// `granularity` is the granularity to open at (defaults to the first of `granularities`,
// or 'daily' if neither is known); `granularities` is the full list available for this
// plot, used to populate the panel's switcher (omitted -> no switcher, single 'daily').
// `multi`/`itemIndex` are for radiosonde-style plots with more than one image per day
// (see loadPanelImage); `itemIndex` defaults to the first item.
async function populateTile(plotId, i, changeUrlParams=true, granularity=null, granularities=null, multi=false, itemIndex=null){
    const list = (granularities && granularities.length) ? granularities : [granularity || 'daily'];
    const gran = granularity || list[0];
    try {
        panelPlotMeta[i] = { plotId, granularities: list, current: gran, multi, itemCount: 0, itemIndex: 0 };
        await loadPanelImage(i, itemIndex || 0);
        renderGranularitySwitcher(i);
        if(changeUrlParams) {
            params.set(panelParam(i), panelUrlValue(i).join(','));
            pushUrl();
        }
        await renderBreadcrumb(i);
    } catch (error) {
        alert('Error: ' + error.message); // display an error message in an alert
    }
};

// Render the panel's granularity switcher (a small header-bar like the search-results
// category headers) from panelPlotMeta[i]; hidden when the plot has one granularity.
function renderGranularitySwitcher(i) {
    const bar = panelEl(i).querySelector('.granularity-switcher');
    if (!bar) return;
    const meta = panelPlotMeta[i];
    if (!meta || meta.granularities.length <= 1) {
        bar.innerHTML = '';
        bar.style.display = 'none';
        return;
    }
    bar.style.display = 'flex';
    bar.innerHTML = meta.granularities.map((g) =>
        `<button type="button" class="granularity-btn${g === meta.current ? ' active' : ''}" onclick="selectGranularity(${i}, '${g}')">${g}</button>`
    ).join('');
}

// Switch an already-open panel's plot to a different granularity. Delegates to
// loadPanelImage so switching back to `daily` on a `multi` plot re-triggers the
// item-count flow instead of just assigning a single-image URL. Also updates the
// pN URL param so the newly-selected granularity is linkable.
function selectGranularity(i, gran) {
    const meta = panelPlotMeta[i];
    if (!meta || gran === meta.current) return;
    meta.current = gran;
    loadPanelImage(i, 0).then(() => {
        renderGranularitySwitcher(i);
        params.set(panelParam(i), panelUrlValue(i).join(','));
        pushUrl();
    });
}

// Render the panel's item switcher (radiosonde-style plots with more than one image
// per day, see loadPanelImage); hidden unless the plot is `multi`, currently viewed
// at `daily`, and actually has more than one item for the current date. Reuses the
// granularity switcher's pill-button look via the shared .granularity-btn class.
function renderItemSwitcher(i) {
    const bar = panelEl(i).querySelector('.item-switcher');
    if (!bar) return;
    const meta = panelPlotMeta[i];
    if (!meta || !meta.multi || meta.current !== 'daily' || meta.itemCount <= 1) {
        bar.innerHTML = '';
        bar.style.display = 'none';
        return;
    }
    bar.style.display = 'flex';
    bar.innerHTML = Array.from({ length: meta.itemCount }, (_, idx) =>
        `<button type="button" class="granularity-btn${idx === meta.itemIndex ? ' active' : ''}" onclick="selectItem(${i}, ${idx})">${idx + 1}</button>`
    ).join('');
}

// Switch to a different item (e.g. launch) of an already-open multi-item panel.
// Each item's URL is directly addressable by index, so this is purely client-side.
function selectItem(i, idx) {
    const meta = panelPlotMeta[i];
    if (!meta || idx === meta.itemIndex) return;
    meta.itemIndex = idx;
    const ymd = document.getElementById("datePicker").valueAsDate.toISOString().slice(0, 10).replace(/-/g, '');
    panelImg(i).src = plotItemUrl(meta.plotId, ymd, idx);
    updatePanelCredit(i);
    renderItemSwitcher(i);
}

// Up/Down arrow navigation: step every open multi-item panel's shown item by `delta`
// (+1/-1), clamped to its available range. Returns whether any panel actually moved,
// so the caller can decide whether to suppress the arrow key's default page scroll.
function stepItem(delta) {
    let stepped = false;
    for (const i of currentOpenPanels) {
        const meta = panelPlotMeta[i];
        if (!meta || !meta.multi || meta.current !== 'daily' || meta.itemCount <= 1) continue;
        const idx = Math.min(Math.max(meta.itemIndex + delta, 0), meta.itemCount - 1);
        if (idx === meta.itemIndex) continue;
        selectItem(i, idx);
        stepped = true;
    }
    return stepped;
}

// Build the breadcrumb for `panel` from openPlots: an always-present "Sites" root
// (returns to site selection for this panel) followed by site / instrument links
// and the current plot as a bold, non-clickable pill. Used for filled panels and,
// with an empty tree, to show just "Sites" on empty panels.
async function renderBreadcrumb(panelIdx) {
    const header = panelHeader(panelIdx);
    if (!header) return;
    const tree = openPlots[panelIdx];
    // Resolve ids -> human-readable names for the breadcrumb labels.
    const labels = [
        await siteLabel(tree[0]),
        await instrumentLabel(tree[0], tree[1]),
        tree[2]
    ];
    const sep = '<span class="crumb-sep" aria-hidden="true">›</span>';
    let html = `<a class="crumb" href="?ms=" onclick="breadcrumbNav(${panelIdx}, -1); return false;">Sites</a>`;
    tree.forEach((id, i) => {
        if (!id) return; // skip empty levels (e.g. search-opened plots)
        const label = labels[i] || id;
        if (i < 2) {
            // site -> instruments at that site; instrument -> that instrument's plots
            // (ms filled up to and including this level). Handled in-app so finishing
            // the selection repopulates this same panel's tile.
            const ms = tree.slice(0, i + 1).join(',');
            html += sep + `<a class="crumb" href="?ms=${encodeURIComponent(ms)}" `
                  + `onclick="breadcrumbNav(${panelIdx}, ${i}); return false;" title="${label}">${label}</a>`;
        } else {
            // plot name: the current selection, not clickable
            html += sep + `<span class="crumb crumb-current" title="${label}" aria-current="page">${label}</span>`;
        }
    });
    header.innerHTML = html;
    header.scrollLeft = header.scrollWidth; // keep the current crumb in view when it overflows
};

// Breadcrumb shown at the top of the selection menu while picking a plot. Mirrors
// renderBreadcrumb but for the in-progress tree (no plot yet): the deepest selected
// level is the non-clickable current pill; ancestors (incl. the "Sites" root) are
// links that re-enter the picker at that level via breadcrumbNav.
async function renderMenuBreadcrumb(panelIdx) {
    const bar = document.getElementById('menuBreadcrumb');
    if (!bar) return;
    const tree = openPlots[panelIdx];
    const labels = [await siteLabel(tree[0]), await instrumentLabel(tree[0], tree[1])];
    const depth = tree[1] ? 1 : (tree[0] ? 0 : -1); // deepest selected level
    const sep = '<span class="crumb-sep" aria-hidden="true">›</span>';
    let html = depth === -1
        ? `<span class="crumb crumb-current" aria-current="page">Sites</span>`
        : `<a class="crumb" href="?ms=" onclick="breadcrumbNav(${panelIdx}, -1); return false;">Sites</a>`;
    [0, 1].forEach((i) => {
        const id = tree[i];
        if (!id) return;
        const label = labels[i] || id;
        if (i < depth) {
            const ms = tree.slice(0, i + 1).join(',');
            html += sep + `<a class="crumb" href="?ms=${encodeURIComponent(ms)}" `
                  + `onclick="breadcrumbNav(${panelIdx}, ${i}); return false;" title="${label}">${label}</a>`;
        } else { // current location
            html += sep + `<span class="crumb crumb-current" title="${label}" aria-current="page">${label}</span>`;
        }
    });
    bar.innerHTML = html;
};

// Navigate to breadcrumb `level` for `panel`: -1 = Sites root (site picker),
// 0 = site (instruments at that site), 1 = instrument (that instrument's plots).
// Keep the tree up to and including the level, clear deeper, then run the normal
// changePlot flow bound to this panel so completing the selection repopulates it.
function breadcrumbNav(i, level) {
    const tree = openPlots[i];
    openPlots[i] = [level >= 0 ? (tree[0] || '') : '', level >= 1 ? (tree[1] || '') : '', ''];
    menu_state = openPlots[i].slice(0, -1);
    selectedPanel = i;
    updateMenuUrl();
    changePlot(i);
};

// Lay out the open panels as a balanced grid: cols = ceil(sqrt(n)), filled row by
// row with a trailing partial row centered. Each cell spans 2 column tracks so an
// odd trailing row can be offset by one track to centre it. Narrow screens collapse
// to a single stacked column. Reproduces the original 1-4 layouts exactly.
function updatePanelPositions() {
    const wrapper = document.getElementById('plotsWrapper');
    for (let i = 0; i < MAX_PANELS; i++) panelEl(i).style.display = "none";

    const open = currentOpenPanels;
    const n = open.length;
    if (!n) return;

    const cols = window.innerWidth < 600 ? 1 : Math.ceil(Math.sqrt(n));
    const rows = Math.ceil(n / cols);
    wrapper.style.gridTemplateColumns = `repeat(${cols * 2}, 1fr)`;
    wrapper.style.gridTemplateRows = `repeat(${rows}, 1fr)`;

    open.forEach((idx, k) => {
        const r = Math.floor(k / cols);
        const itemsInRow = Math.min(cols, n - r * cols);
        const colInRow = k - r * cols;
        const colStart = 1 + (cols - itemsInRow) + colInRow * 2; // centre a partial row
        const el = panelEl(idx);
        el.style.display = "flex";
        el.style.gridColumn = `${colStart} / ${colStart + 2}`;
        el.style.gridRow = `${r + 1}`;
    });
}

function updateDate(shift){
    const datePicker = document.getElementById("datePicker");
    const currentDate = new Date(datePicker.value);
    const nextDay = new Date(currentDate);
    nextDay.setDate(currentDate.getDate() + shift);
    // Don't let the arrow buttons move past today.
    const today = new Date(new Date().toISOString().split('T')[0]);
    if (nextDay > today) return;
    datePicker.valueAsDate = nextDay;
    commitDate();
};

// Apply the date currently shown in the picker: re-render the open plots,
// refresh thumbnails, and record the date in the URL. Shared by the arrow
// buttons/keys (updateDate) and the calendar picker's change event.
function commitDate(){
    const datePicker = document.getElementById("datePicker");
    // Guard against future dates typed directly into the field.
    const today = new Date().toISOString().split('T')[0];
    if (datePicker.value > today) {
        datePicker.value = today;
    }
    selectedDate = datePicker.value;
    updateTiles();
    // Multi-item tiles (see createTile) listen on their .tile-items-group wrapper
    // rather than an <img>, since they render a variable number of separate tiles.
    document.querySelectorAll('img, .tile-items-group').forEach((el) => {
        el.dispatchEvent(recalcThumbnailsEvent);
    });
    params.set('date', selectedDate);
    pushUrl();
};

function updateTiles(){
    // Re-render each open panel's plot for the current date, using the stored plot
    // id rather than parsing it back out of the image URL. Keep whichever granularity
    // is currently selected instead of resetting to the default. For multi-item plots,
    // itemIndex is deliberately not carried over -- a new day's items don't correspond
    // to the previous day's, so populateTile resets to item 0.
    for (const i of currentOpenPanels){
        const plotId = openPlots[i][2];
        if (plotId) {
            const meta = panelPlotMeta[i];
            populateTile(plotId, i, false, meta ? meta.current : null, meta ? meta.granularities : null, meta ? meta.multi : false);
        }
    }
};

var mapActive = true;
// Deterministically show the map (used on load / back-forward navigation,
// where we must not rely on the toggle state of mapButton()).
function showMap() {
    exitMenuMode();
    document.getElementById("selectionMenu").style.display = "none";
    document.getElementById("plotsWrapper").style.display = "none";
    document.getElementById('mapFrame').style.display = 'block';
    document.getElementById('mapButton').title = 'Hide Map';
    mapActive = false;
}
function mapButton() {
    exitMenuMode();
    if (mapActive) {
        document.getElementById("selectionMenu").style.display = "none";
        document.getElementById("plotsWrapper").style.display = "none";
        document.getElementById('mapFrame').style.display = 'block';
        document.getElementById('mapButton').title = 'Hide Map';
    } else {
        document.getElementById("selectionMenu").style.display = "none";
        document.getElementById("plotsWrapper").style.display = "grid";
        document.getElementById('mapFrame').style.display = 'none';
        document.getElementById('mapButton').title = 'Show Map';
    };
    mapActive = !mapActive;
};

function treeNavBack() {
    const tree = openPlots[selectedPanel];
    if (tree[1] !== '') {
        // plots view -> instruments view (needs a site to go back to)
        if (!tree[0]) return; // nothing above (search-opened); button is disabled anyway
        openPlots[selectedPanel] = [tree[0], '', ''];
    } else if (tree[0] !== '') {
        // instruments view -> sites view
        openPlots[selectedPanel] = ['', '', ''];
    } else {
        return; // already at the sites view
    }
    menu_state = openPlots[selectedPanel].slice(0,-1);
    updateMenuUrl();
    changePlot(selectedPanel);
};

// Enable the Back button only when there is a level above the one currently shown:
//   sites/search -> nothing above; instruments -> back to sites;
//   plots -> back to instruments, but only if a site is set (search-opened plots have none).
function updateBackButton(state) {
    const btn = document.getElementById('treeNavBack');
    if (!btn) return;
    let canGoBack = false;
    if (state === 'instruments') {
        canGoBack = true;
    } else if (state === 'plots') {
        canGoBack = !!(openPlots[selectedPanel] && openPlots[selectedPanel][0]);
    }
    btn.disabled = !canGoBack;
};

function toggleSearch() {
    const bar = document.getElementById("searchBar");
    bar.classList.toggle("open");
    if (bar.classList.contains("open")) bar.focus();
};

// Contextual header state: while picking a plot, show Back/Close and hide Map/Add.
function enterMenuMode() {
    document.querySelector(".global-controls").classList.add("selecting");
};

function exitMenuMode() {
    document.querySelector(".global-controls").classList.remove("selecting");
    document.getElementById("searchBar").classList.remove("open");
};

function treeNavClose() {
    document.getElementById("selectionMenu").style.display = "none";
    document.getElementById("plotsWrapper").style.display = "grid";
    exitMenuMode();
    menu_state = ['','']
    updateMenuUrl();
};

// Debounced as-you-type entry point (wired to #searchBar oninput).
let searchToken = 0;
let searchDebounce;
function onSearchInput() {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(searchItems, 200);
}

async function searchItems() {
    const grid = document.getElementById('selectionMenu');
    document.getElementById("selectionMenu").style.display = "grid";
    document.getElementById("plotsWrapper").style.display = "none";
    document.getElementById("mapFrame").style.display = "none";
    enterMenuMode();

    const query = document.getElementById("searchBar").value.trim();
    if (!query) {
        grid.innerHTML = '';
        grid.dataset.state = 'search';
        return;
    }

    // Open results into the panel being edited, else the first open panel.
    let panel;
    if (selectedPanel != null && currentOpenPanels.includes(selectedPanel)) {
        panel = selectedPanel;
    } else {
        panel = currentOpenPanels.length ? currentOpenPanels[0] : 0;
        selectedPanel = panel; // keep Back/Close controls in sync
    }

    // Guard against out-of-order responses from rapid typing.
    const token = ++searchToken;
    let data;
    try {
        const res = await fetch(`$APIURL/search/${encodeURIComponent(query.toLowerCase())}`);
        data = await res.json();
    } catch (error) {
        console.error('Search failed:', error);
        return;
    }
    if (token !== searchToken) return; // a newer search superseded this one

    grid.innerHTML = '';
    grid.dataset.state = 'search';
    updateBackButton('search'); // search is not part of the tree nav

    const addSection = (label, entries, makeTile) => {
        const keys = Object.keys(entries || {});
        if (!keys.length) return;
        const header = document.createElement('h3');
        header.className = 'search-section';
        header.textContent = label;
        grid.appendChild(header);
        keys.forEach((key) => grid.appendChild(makeTile(key, entries[key])));
    };

    addSection('Sites', data.sites, (key, value) => createTile(key, value, 'sites', panel, true));
    addSection('Instruments', data.inst, (key, value) => createTile(key, value, 'instruments', panel, true));
    // plots: key is the plotName/visualization id; value is the list of sites it covers (shown as subtitle)
    addSection('Plots', data.plots, (key, value) =>
        createTile(Array.isArray(value) ? value.join(', ') : value, key, 'plots', panel, true));

    if (!grid.children.length) {
        const empty = document.createElement('p');
        empty.className = 'search-empty';
        empty.textContent = 'No matches';
        grid.appendChild(empty);
    }
};