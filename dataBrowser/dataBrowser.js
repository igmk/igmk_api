var currentOpenPanels = ["p1","p2","p3","p4"];
var maxPanels = 4;
const recalcThumbnailsEvent = new CustomEvent('recalcThumbnails',{ detail: { yourData: 'Here is some data' } });
var openPlots = Array(maxPanels).fill().map(() => Array(3).fill(''));
var selectedPanel;

const url = new URL(window.location.href);
const params = url.searchParams;
let selectedDate = params.get('date');
let p1_info = params.get('p1');
let p2_info = params.get('p2');
let p3_info = params.get('p3');
let p4_info = params.get('p4');

document.addEventListener("DOMContentLoaded", function() {
    panels = document.querySelectorAll('.panel');
    setPanelNumber();
    updatePanelPositions(currentOpenPanels);
    if (selectedDate === null) {
        var today = new Date().toISOString().split('T')[0];
        selectedDate = today;
    }
    var dateInput = document.getElementById('datePicker');
    dateInput.value = selectedDate;
    dateInput.addEventListener('change', () => {
        selectedDate = dateInput.value;
        updateTiles();
        const images = document.querySelectorAll('img');
        images.forEach((image) => {
            image.dispatchEvent(recalcThumbnailsEvent);
        });
    });
    if (p1_info !== null) {
        populateTile(p1_info.split(',')[2] , 'p1')
        openPlots[0] = p1_info.split(',')
    }
    if (p2_info !== null) {
        populateTile(p2_info.split(',')[2] , 'p2')
        openPlots[1] = p2_info.split(',')
    }
    if (p3_info !== null) {
        populateTile(p3_info.split(',')[2] , 'p3')
        openPlots[2] = p3_info.split(',')
    }
    if (p4_info !== null) {
        populateTile(p4_info.split(',')[2] , 'p4')
        openPlots[3] = p4_info.split(',')
    }
});

document.addEventListener('keydown', function(event) {
  // Check which key was pressed
  if (event.key === 'a' || event.key === 'ArrowLeft') {
    // Execute your function here
    updateDate(-1);
  } else if (event.key === 's'|| event.key === 'ArrowRight'){
    updateDate(1);
  }
});

window.addEventListener("resize", function() {
    setPanelNumber();
    updatePanelPositions(currentOpenPanels);
});

function setPanelNumber() {
    if (window.innerWidth < 500){
        maxPanels = 2;
        currentOpenPanels.splice(2);
    } else {
        maxPanels = 4;
    }
    if (openPlots.length < maxPanels){
        Array.from({length: maxPanels - openPlots.length}, () => myList.push(Array(3).fill('')));
    }
};

function newPanel() {
    if (currentOpenPanels.length < maxPanels) {
        var allIds = Array.from(panels).map(div => div.id);
        var availablePanels = allIds.filter(item => !currentOpenPanels.includes(item));
        var newPanel = availablePanels[0];
        currentOpenPanels.push(newPanel);
        updatePanelPositions(currentOpenPanels);
    }
};

function closePanel(button) {
    var panel = document.getElementById(button).parentNode.parentNode.id;
    var index = currentOpenPanels.indexOf(panel);
    if (index > -1) {
        currentOpenPanels.splice(index, 1); 
    }
    updatePanelPositions(currentOpenPanels);
};

function openSelectionMenu(button) {
    var panel = document.getElementById(button).parentNode.parentNode.id;
    var index = currentOpenPanels.indexOf(panel);
    document.getElementById("selectionMenu").style.display = "grid";
    document.getElementById("plotsWrapper").style.display = "none";
};

function closeSelectionMenu() {
    document.getElementById("selectionMenu").style.display = "none";
    document.getElementById("plotsWrapper").style.display = "grid";
};

async function changePlot(panel) {
    selectedPanel = parseInt(panel[1]) - 1;
    var currentPlotTree = openPlots[parseInt(panel[1]) -1]
    document.getElementById("selectionMenu").style.display = "grid";
    document.getElementById("plotsWrapper").style.display = "none";
    if (currentPlotTree[1] !=''){
        getPlots(currentPlotTree[1], panel)
    } else if (currentPlotTree[0] !='') {
        getInstruments(currentPlotTree[0], panel)
    } else {
        try {
            const response = await fetch('https://134.95.211.183:8000/sites');
            const data = await response.json();
            populateGrid(data,"sites",panel);
        }
        catch (error) {
            alert('Error: ' + error.message); // display an error message in an alert
        }
    }
};

function populateGrid(data,state,panel) {         
    const grid = document.getElementById('selectionMenu');
    grid.innerHTML = '';

    const entries = Object.entries(data);
    entries.forEach(([key, value]) => {
        // ---- create tile element ----
        const tile = document.createElement('div');
        tile.className = 'tile';

        // ---- tile content ----
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
        tile.appendChild(img)

        if (state==="sites") {
            tile.addEventListener('click', () => {
                openPlots[parseInt(panel[1]) -1] = [key, '', ''];
                getInstruments(key,panel);
            });
        } else if (state==="instruments"){
            tile.addEventListener('click', () => {
                openPlots[parseInt(panel[1])-1][1] = key;
                openPlots[parseInt(panel[1])-1][2] = '';
                getPlots(key,panel);
            });
            valueEl.textContent = value.description 
        } else if (state==="plots"){
            const ymd = document.getElementById("datePicker").valueAsDate.toISOString().slice(0, 10).replace(/-/g, '');
            img.src = 'https://134.95.211.183:8000/visualizations/byID/'+value+'/'+ymd;
            img.onerror = function() {
                tile.style.display = "none";
            };
            img.addEventListener('recalcThumbnails', () => {
                const ymd = document.getElementById("datePicker").valueAsDate.toISOString().slice(0, 10).replace(/-/g, '');
                img.src = 'https://134.95.211.183:8000/visualizations/byID/'+value+'/'+ymd;
                tile.style.display = "block";
                img.onerror = function() {
                    tile.style.display = "none";
                };
            });
            tile.addEventListener('click', () => {
                openPlots[parseInt(panel[1])-1][2] = value;
                populateTile(value,panel);
                document.getElementById("selectionMenu").style.display = "none";
                document.getElementById("plotsWrapper").style.display = "grid";   
            });
        } else {alert("unknown state")} 

        // ---- add tile to the grid ----
        grid.appendChild(tile);

    });

  };

async function getInstruments(siteId,panel) {
    try {
        const response = await fetch('https://134.95.211.183:8000/sites/'+siteId+'/instruments');
        const data = await response.json();
        populateGrid(data,"instruments",panel);
    } catch (error) {
        alert('Error: ' + error.message); // display an error message in an alert
    }
};
async function getPlots(instrumentId,panel){
    try {
        const response = await fetch('https://134.95.211.183:8000/visualizations/byInstrument/'+instrumentId);
        const data = await response.json();
        populateGrid(data,"plots",panel);
    } catch (error) {
        alert('Error: ' + error.message); // display an error message in an alert
    }
};
async function populateTile(plotId,panel){
    const ymd = document.getElementById("datePicker").valueAsDate.toISOString().slice(0, 10).replace(/-/g, '');
    try {
        const imageContainer = document.getElementById(panel);
        const image = imageContainer.querySelector('img');
        image.src = 'https://134.95.211.183:8000/visualizations/byID/'+plotId+'/'+ymd;
        params.set(panel, openPlots[parseInt(panel[1]) -1].join(','));
        const newUrl = `${window.location.pathname}?${params.toString()}`;
        window.history.pushState({}, '', newUrl);
        const header = document.getElementById(`header${parseInt(panel[1])}`);
        header.innerHTML = openPlots[parseInt(panel[1]) -1].join('\t');
        console.log('https://134.95.211.183:8000/instruments/'+openPlots[parseInt(panel[1]) -1][1]);
        const response = await fetch('https://134.95.211.183:8000/instruments/'+openPlots[parseInt(panel[1]) -1][1]);
        const data = await response.json();
        const info = document.getElementById(`info${parseInt(panel[1])}`);
        info.href = data.wiki

    } catch (error) {
        alert('Error: ' + error.message); // display an error message in an alert
    }
};

function updatePanelPositions(openPanels) {
    panels.forEach(element => {
        element.style.display = 'none';
    });
    var len = openPanels.length;
    if (len == 4) {
        var panel = document.getElementById(openPanels[0]);
        panel.style.display = "block";
        panel.style.gridColumn = "1 / 3";
        panel.style.gridRow = "1 / 3";
        var panel = document.getElementById(openPanels[1]);
        panel.style.display = "block";
        panel.style.gridColumn = "3 / 5";
        panel.style.gridRow = "1 / 3";
        var panel = document.getElementById(openPanels[2]);
        panel.style.display = "block";
        panel.style.gridColumn = "1 / 3";
        panel.style.gridRow = "3 / 5";
        var panel = document.getElementById(openPanels[3]);
        panel.style.display = "block";
        panel.style.gridColumn = "3 / 5";
        panel.style.gridRow = "3 / 5";
    } else if (len == 3) {
        panel = document.getElementById(openPanels[0]);
        panel.style.display = "block";
        panel.style.gridColumn = "1 / 3";
        panel.style.gridRow = "1 / 3";
        panel = document.getElementById(openPanels[1]);
        panel.style.display = "block";
        panel.style.gridColumn = "3 / 5";
        panel.style.gridRow = "1 / 3";
        panel = document.getElementById(openPanels[2]);
        panel.style.display = "block";
        panel.style.gridColumn = "2 / 4";
        panel.style.gridRow = "3 / 5";
    } else if (len == 2) {
        if (maxPanels == 4) {
            panel = document.getElementById(openPanels[0]);
            panel.style.display = "block";
            panel.style.gridColumn = "1 / 3";
            panel.style.gridRow = "1 / 5";
            panel = document.getElementById(openPanels[1]);
            panel.style.display = "block";
            panel.style.gridColumn = "3 / 5";
            panel.style.gridRow = "1 / 5";
        } else if (maxPanels == 2) {
            panel = document.getElementById(openPanels[0]);
            panel.style.display = "block";
            panel.style.gridColumn = "1 / 5";
            panel.style.gridRow = "1 / 3";
            panel = document.getElementById(openPanels[1]);
            panel.style.display = "block";
            panel.style.gridColumn = "1 / 5";
            panel.style.gridRow = "3 / 5";
        }
    } else if (len == 1) {
        panel = document.getElementById(openPanels[0]);
        panel.style.display = "block";
        panel.style.gridColumn = "1 / 5";
        panel.style.gridRow = "1 / 5";
    }
    
};

function updateDate(shift){
    datePicker = document.getElementById("datePicker")
    const currentDate = new Date(datePicker.value); // get the current date
    const nextDay = new Date(currentDate); // create a new date object with the same value as currentDate
    nextDay.setDate(currentDate.getDate() + shift); // add one day to the new date object
    datePicker.valueAsDate = nextDay;
    updateTiles();
    const images = document.querySelectorAll('img');
    images.forEach((image) => {
        image.dispatchEvent(recalcThumbnailsEvent);
    });
    params.set('date', datePicker.value);
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({}, '', newUrl);
};

function updateTiles(){
    var panels=['p1','p2','p3','p4']
    for (const panel of panels){
        const imageContainer = document.getElementById(panel);
        const image = imageContainer.querySelector('img');
        const plotUrl = image.src;
        const plotId = plotUrl.split('/')[5];
        populateTile(plotId,panel);
    };
};
var mapActive = true;
function mapButton() {
    if (mapActive) {
        document.getElementById("selectionMenu").style.display = "none";
        document.getElementById("plotsWrapper").style.display = "none";
        document.getElementById('mapFrame').style.display = 'block';
        document.getElementById('mapButton').textContent = 'Hide Map';
    } else {
        document.getElementById("selectionMenu").style.display = "none";
        document.getElementById("plotsWrapper").style.display = "grid";
        document.getElementById('mapFrame').style.display = 'none';
        document.getElementById('mapButton').textContent = 'Show Map';

    };
    mapActive = !mapActive;
};

function treeNavBack() {
    var level = openPlots[selectedPanel].indexOf('');
    if (level === -1 || level === 2) {
        openPlots[selectedPanel][1] = '';
        openPlots[selectedPanel][2] = '';
    } else if (level === 1){
        openPlots[selectedPanel] = Array(3).fill('');
    } else {
        console.log('Error w/ back button');
    }
    changePlot(`p${selectedPanel+1}`);
};

function treeNavClose() {
    document.getElementById("selectionMenu").style.display = "none";
    document.getElementById("plotsWrapper").style.display = "grid";
};