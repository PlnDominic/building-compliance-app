console.log("Script started");

let map = L.map('map').setView([6.4556, -2.317], 13);

// Define base layers
let osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
});

let googleSat = L.tileLayer('http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
    maxZoom: 20,
    subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
    attribution: '© Google'
});

let googleHybrid = L.tileLayer('http://{s}.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}', {
    maxZoom: 20,
    subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
    attribution: '© Google'
});

// Add the Google Hybrid layer as the default base layer
googleHybrid.addTo(map);

let bibianiLayer = L.layerGroup().addTo(map);
let plotsLayer = L.layerGroup().addTo(map);

let baseMaps = {
    "Google Hybrid": googleHybrid,
    "Google Satellite": googleSat,
    "OpenStreetMap": osm
};

let overlayMaps = {
    "Bibiani Layout": bibianiLayer,
    "Plots": plotsLayer
};

L.control.layers(baseMaps, overlayMaps).addTo(map);

let currentGeometry = null;
let editingPlotId = null;

// Initialize the FeatureGroup to store editable layers
var editableLayers = new L.FeatureGroup();
map.addLayer(editableLayers);

// Initialize draw control
var drawControl = new L.Control.Draw({
    edit: {
        featureGroup: editableLayers
    },
    draw: {
        polygon: true,
        polyline: false,
        rectangle: false,
        circle: false,
        marker: false,
        circlemarker: false
    }
});
map.addControl(drawControl);

// Event listener for draw:created
map.on('draw:created', function(e) {
    var type = e.layerType,
        layer = e.layer;

    if (type === 'polygon') {
        editableLayers.addLayer(layer);
        currentGeometry = layer.toGeoJSON().geometry;
        fillFormWithLayoutData({});  // Reset form for new plot
    }
});

// Function to load Bibiani layout
function loadBibianiLayout() {
    fetch('/bibiani_layout')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                console.warn('Warning for Bibiani layout:', data.error);
                return;
            }
            L.geoJSON(data, {
                style: function(feature) {
                    return {
                        color: 'blue',
                        weight: 2,
                        fillOpacity: 0.1
                    };
                },
                onEachFeature: function(feature, layer) {
                    layer.on('click', function(e) {
                        currentGeometry = feature.geometry;
                        fillFormWithLayoutData(feature.properties);
                    });
                    if (feature.properties) {
                        layer.bindPopup(createPopupContent(feature.properties));
                    }
                }
            }).addTo(bibianiLayer);
            console.log('Bibiani layout loaded successfully');
            loadPlots();
        })
        .catch(error => {
            console.error('Error fetching Bibiani layout:', error);
        });
}

// Function to load plots
function loadPlots() {
    fetch('/plots')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(plots => {
            if (!Array.isArray(plots)) {
                console.error('Received data is not an array:', plots);
                return;
            }
            plotsLayer.clearLayers();
            plots.forEach(plot => {
                if (plot.geom) {
                    L.geoJSON(plot.geom, {
                        style: function(feature) {
                            return {
                                color: getComplianceColor(plot.compliance_status),
                                weight: 2,
                                fillOpacity: 0.5
                            };
                        },
                        onEachFeature: function(feature, layer) {
                            layer.bindPopup(createPopupContent(plot));
                        }
                    }).addTo(plotsLayer);
                } else {
                    console.warn('Plot has no geometry:', plot);
                }
            });
        })
        .catch(error => {
            console.error('Error fetching plots:', error);
        });
}

// Function to get compliance color
function getComplianceColor(status) {
    switch (status) {
        case 'compliant':
            return 'green';
        case 'non-compliant':
            return 'red';
        case 'partial':
            return 'yellow';
        default:
            return 'gray';
    }
}

// Function to create popup content
function createPopupContent(properties) {
    let content = '<div>';
    for (let key in properties) {
        if (properties.hasOwnProperty(key) && key !== 'geom') {
            content += `<strong>${key}:</strong> ${properties[key]}<br>`;
        }
    }
    content += '</div>';
    return content;
}

// Function to fill form with layout data
function fillFormWithLayoutData(properties) {
    document.getElementById('plot-number').value = properties.plot_number || '';
    document.getElementById('owner-name').value = properties.owner_name || '';
    document.getElementById('address').value = properties.address || '';
    document.getElementById('area-sqm').value = properties.area_sqm || '';
    document.getElementById('compliance-status').value = properties.compliance_status || '';
    document.getElementById('land-use').value = properties.land_use || '';
    document.getElementById('development-status').value = properties.development_status || '';
    document.getElementById('additional-info').value = properties.additional_info || '';
}

// Event listener for form submission
document.getElementById('plot-form').addEventListener('submit', function(e) {
    e.preventDefault();
    if (!currentGeometry) {
        alert('Please draw a plot on the map first.');
        return;
    }

    const formData = new FormData(this);
    formData.append('geom', JSON.stringify(currentGeometry));

    // Append the file if it exists
    const imageFile = document.getElementById('image').files[0];
    if (imageFile) {
        formData.append('image', imageFile);
    }

    const url = editingPlotId ? `/plots/${editingPlotId}` : '/plots';
    const method = editingPlotId ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        body: formData,
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => {
                throw err;
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Plot saved:', data);
        resetForm();
        refreshLayout();
        alert('Plot saved successfully!');
    })
    .catch((error) => {
        console.error('Error saving plot:', error);
        alert(`Error saving plot: ${error.error || 'Unknown error'}`);
    });
});

// Function to reset form
function resetForm() {
    document.getElementById('plot-form').reset();
    document.getElementById('plot-id').value = '';
    editingPlotId = null;
    currentGeometry = null;
    document.getElementById('form-title').textContent = 'Add New Plot';
    document.getElementById('cancel-edit').style.display = 'none';
    editableLayers.clearLayers();
}

// Event listener for cancel edit button
document.getElementById('cancel-edit').addEventListener('click', resetForm);

// Function to refresh the layout
function refreshLayout() {
    bibianiLayer.clearLayers();
    plotsLayer.clearLayers();
    editableLayers.clearLayers();
    loadBibianiLayout();
}

// Load the Bibiani layout
loadBibianiLayout();

// Responsive design
function checkScreenSize() {
    if (window.innerWidth <= 768) {
        // No sidebar collapse functionality anymore
    } else {
        // No sidebar collapse functionality anymore
    }
    map.invalidateSize();
}

window.addEventListener('load', checkScreenSize);
window.addEventListener('resize', checkScreenSize);

//coordinate on mousemove
map.on("mousemove", function(e){
    $("#cord").html(`Lat:${e.latlng.lat.toFixed(6)}, lng:${e.latlng.lng.toFixed(6)}`)
})

//Print map
L.control.browserPrint({position: 'topleft'}).addTo(map);

//Add Scale
L.control.scale({position: "bottomleft"}).addTo(map)

// Add a control to show user's location
var locateControl = L.control.locate({
    position: 'topleft',
    strings: {
        title: "Show me where I am",
    },
    onLocationError: function(e) {
        alert(e.message);
    },
    onLocationFound: function(e) {
        var radius = e.accuracy / 2;

        L.marker(e.latlng).addTo(map)
            .bindPopup("You are within " + radius + " meters from this point").openPopup();

        L.circle(e.latlng, radius).addTo(map);
    }
}).addTo(map);

// Add multi-location zoom feature
var multiLocationControl = L.Control.extend({
    options: {
        position: 'topleft'
    },

    onAdd: function (map) {
        var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
        container.innerHTML = '<a href="#" title="Multi-location Zoom" style="font-size: 18px;">📍</a>';
        container.onclick = this._onClick;
        return container;
    },

    _onClick: function (e) {
        e.preventDefault();
        openCoordinateModal();
    }
});

map.addControl(new multiLocationControl());

function openCoordinateModal() {
    var modal = document.createElement('div');
    modal.style.position = 'fixed';
    modal.style.left = '50%';
    modal.style.top = '50%';
    modal.style.transform = 'translate(-50%, -50%)';
    modal.style.backgroundColor = 'white';
    modal.style.padding = '20px';
    modal.style.borderRadius = '5px';
    modal.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
    modal.style.zIndex = '1000';

    modal.innerHTML = `
        <h3>Enter Coordinates</h3>
        <input type="text" id="coord1" placeholder="Lat, Lng for point 1"><br><br>
        <input type="text" id="coord2" placeholder="Lat, Lng for point 2"><br><br>
        <input type="text" id="coord3" placeholder="Lat, Lng for point 3"><br><br>
        <input type="text" id="coord4" placeholder="Lat, Lng for point 4"><br><br>
        <button id="saveCoords">Save</button>
        <button id="cancelCoords">Cancel</button>
    `;

    document.body.appendChild(modal);

    document.getElementById('saveCoords').onclick = function() {
        var coords = [
            document.getElementById('coord1').value.split(',').map(Number),
            document.getElementById('coord2').value.split(',').map(Number),
            document.getElementById('coord3').value.split(',').map(Number),
            document.getElementById('coord4').value.split(',').map(Number)
        ];

        if (coords.some(coord => coord.length !== 2 || coord.some(isNaN))) {
            alert('Please enter valid coordinates in the format "Lat, Lng"');
            return;
        }

        drawPolygon(coords);
        document.body.removeChild(modal);
    };

    document.getElementById('cancelCoords').onclick = function() {
        document.body.removeChild(modal);
    };
}

function drawPolygon(coords) {
    editableLayers.clearLayers();
    var polygon = L.polygon(coords, {color: 'red'}).addTo(editableLayers);
    map.fitBounds(polygon.getBounds());

    currentGeometry = polygon.toGeoJSON().geometry;

    // Save the polygon to the database
    savePolygon(coords);
}

function savePolygon(coords) {
    fetch('/save_polygon', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            geom: coords
        }),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Polygon coordinates saved:', data);
        alert('Polygon coordinates saved successfully! Please enter plot details.');
        openPlotDetailsModal(coords);
    })
    .catch((error) => {
        console.error('Error saving polygon coordinates:', error);
        alert('Error saving polygon coordinates. Please try again.');
    });
}

function openPlotDetailsModal(coords) {
    var modal = document.createElement('div');
    modal.style.position = 'fixed';
    modal.style.left = '50%';
    modal.style.top = '50%';
    modal.style.transform = 'translate(-50%, -50%)';
    modal.style.backgroundColor = 'white';
    modal.style.padding = '20px';
    modal.style.borderRadius = '5px';
    modal.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
    modal.style.zIndex = '1000';

    modal.innerHTML = `
        <h3>Enter Plot Details</h3>
        <input type="text" id="plot_number" placeholder="Plot Number"><br><br>
        <input type="text" id="owner_name" placeholder="Owner Name"><br><br>
        <input type="text" id="address" placeholder="Address"><br><br>
        <input type="number" id="area_sqm" placeholder="Area (sq m)"><br><br>
        <select id="compliance_status">
            <option value="">Select Compliance Status</option>
            <option value="compliant">Compliant</option>
            <option value="non-compliant">Non-Compliant</option>
            <option value="partial">Partial Compliance</option>
        </select><br><br>
        <input type="text" id="land_use" placeholder="Land Use"><br><br>
        <input type="text" id="development_status" placeholder="Development Status"><br><br>
        <textarea id="additional_info" placeholder="Additional Info"></textarea><br><br>
        <button id="savePlotDetails">Save</button>
        <button id="cancelPlotDetails">Cancel</button>
    `;

    document.body.appendChild(modal);

    document.getElementById('savePlotDetails').onclick = function() {
        var plotDetails = {
            plot_number: document.getElementById('plot_number').value,
            owner_name: document.getElementById('owner_name').value,
            address: document.getElementById('address').value,
            area_sqm: document.getElementById('area_sqm').value,
            compliance_status: document.getElementById('compliance_status').value,
            land_use: document.getElementById('land_use').value,
            development_status: document.getElementById('development_status').value,
            additional_info: document.getElementById('additional_info').value,
            geom: coords
        };

        savePlotToCadastra(plotDetails);
        document.body.removeChild(modal);
    };

    document.getElementById('cancelPlotDetails').onclick = function() {
        document.body.removeChild(modal);
    };
}

function savePlotToCadastra(plotDetails) {
    fetch('/save_cadastra', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(plotDetails),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Plot details saved:', data);
        alert('Plot details saved successfully!');
        refreshLayout();
    })
    .catch((error) => {
        console.error('Error saving plot details:', error);
        alert('Error saving plot details. Please try again.');
    });
}

console.log("Script finished");