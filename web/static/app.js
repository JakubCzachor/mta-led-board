// MTA LED Board - Frontend JavaScript
const API_BASE = '';
const REFRESH_INTERVAL = 2000; // 2 seconds

let currentTab = 'busiest';
let searchTimeout = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initSearch();
    initStationDetail();
    startDataRefresh();
});

// Tab management
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    currentTab = tabName;

    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update panes
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.toggle('active', pane.id === `tab-${tabName}`);
    });
}

// Search functionality
function initSearch() {
    const searchInput = document.getElementById('station-search');
    const searchResults = document.getElementById('search-results');

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();

        if (searchTimeout) clearTimeout(searchTimeout);

        if (query.length < 2) {
            searchResults.classList.add('hidden');
            return;
        }

        searchTimeout = setTimeout(() => {
            performSearch(query);
        }, 300);
    });

    // Click outside to close
    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.classList.add('hidden');
        }
    });
}

async function performSearch(query) {
    const searchResults = document.getElementById('search-results');

    try {
        const response = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (data.stations.length === 0) {
            searchResults.innerHTML = '<div class="search-result-item">No stations found</div>';
        } else {
            searchResults.innerHTML = data.stations.map(station => {
                const routesHtml = station.has_trains
                    ? station.routes.map(r => createRouteBadge(r)).join('')
                    : '<span class="search-no-trains">No trains currently</span>';

                return `
                    <div class="search-result-item" onclick="showStationDetail('${station.key}')">
                        <div class="search-result-name">${escapeHtml(station.name)}</div>
                        <div class="search-result-routes">${routesHtml}</div>
                    </div>
                `;
            }).join('');
        }

        searchResults.classList.remove('hidden');
    } catch (error) {
        console.error('Search error:', error);
        searchResults.innerHTML = '<div class="search-result-item">Error performing search</div>';
        searchResults.classList.remove('hidden');
    }
}

// Station detail view
function initStationDetail() {
    document.getElementById('close-detail').addEventListener('click', () => {
        document.getElementById('station-detail').classList.add('hidden');
    });
}

async function showStationDetail(stationKey) {
    const detailView = document.getElementById('station-detail');
    const searchResults = document.getElementById('search-results');

    searchResults.classList.add('hidden');

    try {
        const response = await fetch(`${API_BASE}/api/station/${stationKey}`);
        if (!response.ok) {
            alert('Station not found or no trains currently');
            return;
        }

        const station = await response.json();

        document.getElementById('detail-name').textContent = station.name;
        document.getElementById('detail-status').textContent = station.mode_name;
        document.getElementById('detail-status').className = `status-badge ${station.mode_name}`;
        document.getElementById('detail-description').textContent = station.status;

        const routesHtml = station.routes.map(r => createRouteBadge(r)).join('');
        document.getElementById('detail-routes').innerHTML = routesHtml;

        detailView.classList.remove('hidden');
        detailView.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (error) {
        console.error('Error fetching station detail:', error);
        alert('Error loading station details');
    }
}

// Data refresh
function startDataRefresh() {
    refreshData();
    setInterval(refreshData, REFRESH_INTERVAL);
}

async function refreshData() {
    try {
        const [statsData, stationsData] = await Promise.all([
            fetch(`${API_BASE}/api/statistics`).then(r => r.json()),
            fetch(`${API_BASE}/api/stations`).then(r => r.json()),
        ]);

        updateStatus(statsData.last_update);
        updateStatistics(statsData);
        updateBusiestStations(statsData.busiest_stations);
        updateActiveRoutes(statsData.active_routes);
        updateAllStations(stationsData.stations);
    } catch (error) {
        console.error('Error refreshing data:', error);
        document.getElementById('status-indicator').textContent = 'ERROR';
        document.getElementById('status-indicator').className = 'status-error';
    }
}

function updateStatus(lastUpdate) {
    const now = Date.now() / 1000;
    const age = now - lastUpdate;

    const indicator = document.getElementById('status-indicator');
    const updateText = document.getElementById('last-update');

    if (age < 10) {
        indicator.textContent = 'LIVE';
        indicator.className = 'status-ok';
    } else if (age < 60) {
        indicator.textContent = 'UPDATING';
        indicator.className = 'status-stale';
    } else {
        indicator.textContent = 'STALE';
        indicator.className = 'status-error';
    }

    const date = new Date(lastUpdate * 1000);
    updateText.textContent = `Updated: ${date.toLocaleTimeString()}`;
}

function updateStatistics(stats) {
    document.getElementById('stat-active-stations').textContent = stats.active_stations;
    document.getElementById('stat-total-vehicles').textContent = stats.total_vehicles;
    document.getElementById('stat-stopped').textContent = stats.mode_breakdown.STOPPED_AT || 0;
    document.getElementById('stat-incoming').textContent = stats.mode_breakdown.INCOMING || 0;
    document.getElementById('stat-departing').textContent = stats.mode_breakdown.DEPARTING || 0;
}

function updateBusiestStations(stations) {
    const container = document.getElementById('busiest-stations-list');
    if (stations.length === 0) {
        container.innerHTML = '<p style="color: var(--text-secondary); padding: 20px;">No active stations</p>';
        return;
    }

    container.innerHTML = stations.map(station => `
        <div class="station-item" onclick="showStationDetail('${station.key}')">
            <div class="station-item-header">
                <span class="station-name">${escapeHtml(station.name)}</span>
                <span class="station-mode ${station.mode_name}">${station.mode_name}</span>
            </div>
            <div class="route-list">
                ${station.routes.map(r => createRouteBadge(r)).join('')}
                <span style="color: var(--text-secondary); font-size: 0.9rem; margin-left: 10px;">
                    ${station.route_count} route${station.route_count !== 1 ? 's' : ''}
                </span>
            </div>
        </div>
    `).join('');
}

function updateActiveRoutes(routes) {
    const container = document.getElementById('active-routes-list');
    if (routes.length === 0) {
        container.innerHTML = '<p style="color: var(--text-secondary); padding: 20px;">No active routes</p>';
        return;
    }

    container.innerHTML = routes.map(route => `
        <div class="route-stat-item">
            <div class="route-stat-badge" data-route="${route.route}" style="${getRouteStyle(route.route)}">
                ${route.route}
            </div>
            <div class="route-stat-info">
                <div class="route-stat-name">${route.route} Train</div>
                <div class="route-stat-count">${route.station_count} station${route.station_count !== 1 ? 's' : ''}</div>
            </div>
        </div>
    `).join('');
}

function updateAllStations(stations) {
    const container = document.getElementById('all-stations-list');
    if (stations.length === 0) {
        container.innerHTML = '<p style="color: var(--text-secondary); padding: 20px;">No active stations</p>';
        return;
    }

    container.innerHTML = stations.filter(s => s.routes.length > 0).map(station => `
        <div class="station-item" onclick="showStationDetail('${station.key}')">
            <div class="station-item-header">
                <span class="station-name">${escapeHtml(station.name)}</span>
                <span class="station-mode ${station.mode_name}">${station.mode_name}</span>
            </div>
            <div class="route-list">
                ${station.routes.map(r => createRouteBadge(r)).join('')}
            </div>
        </div>
    `).join('');
}

// Helper functions
function createRouteBadge(route) {
    return `<span class="route-badge" data-route="${route}">${route}</span>`;
}

function getRouteStyle(route) {
    const colors = {
        '1': '#ee352e', '2': '#ee352e', '3': '#ee352e',
        '4': '#00933c', '5': '#00933c', '6': '#00933c',
        '7': '#b933ad',
        'A': '#0039a6', 'C': '#0039a6', 'E': '#0039a6',
        'B': '#ff6319', 'D': '#ff6319', 'F': '#ff6319', 'M': '#ff6319',
        'G': '#6cbe45',
        'J': '#996633', 'Z': '#996633',
        'L': '#a7a9ac',
        'N': '#fccc0a', 'Q': '#fccc0a', 'R': '#fccc0a', 'W': '#fccc0a',
        'S': '#808183', 'SI': '#808183',
    };

    const bg = colors[route] || '#808183';
    const textColor = ['L', 'N', 'Q', 'R', 'W'].includes(route) ? 'black' : 'white';

    return `background: ${bg}; color: ${textColor};`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
