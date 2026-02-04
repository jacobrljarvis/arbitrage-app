// Sports Betting Arbitrage Scanner - Frontend Logic

const API_BASE = '/api';

// State
let currentOpportunities = [];
let selectedOpportunity = null;

// DOM Elements
const sportSelect = document.getElementById('sport-select');
const minProfitInput = document.getElementById('min-profit');
const totalStakeInput = document.getElementById('total-stake');
const scanBtn = document.getElementById('scan-btn');
const scanInfo = document.getElementById('scan-info');
const eventsScanned = document.getElementById('events-scanned');
const opportunitiesFound = document.getElementById('opportunities-found');
const scanTime = document.getElementById('scan-time');
const noOpportunities = document.getElementById('no-opportunities');
const opportunitiesTable = document.getElementById('opportunities-table');
const opportunitiesBody = document.getElementById('opportunities-body');
const stakeCalculator = document.getElementById('stake-calculator');
const modalStake = document.getElementById('modal-stake');
const eventDetails = document.getElementById('event-details');
const stakeResults = document.getElementById('stake-results');
const errorMessage = document.getElementById('error-message');
const apiRemaining = document.getElementById('api-remaining');
const apiUsedMonth = document.getElementById('api-used-month');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await loadSports();
    await loadApiUsage();

    scanBtn.addEventListener('click', handleScan);

    // Close modal on outside click
    stakeCalculator.addEventListener('click', (e) => {
        if (e.target === stakeCalculator) {
            closeModal();
        }
    });

    // Close modal on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
        }
    });
});

// Load available sports
async function loadSports() {
    try {
        const response = await fetch(`${API_BASE}/sports`);
        if (!response.ok) throw new Error('Failed to load sports');

        const sports = await response.json();

        sportSelect.innerHTML = '<option value="">Select a sport...</option>';
        sports.forEach(sport => {
            const option = document.createElement('option');
            option.value = sport.key;
            option.textContent = sport.title;
            sportSelect.appendChild(option);
        });
    } catch (error) {
        showError('Failed to load sports. Make sure the server is running.');
        console.error('Error loading sports:', error);
    }
}

// Load API usage stats
async function loadApiUsage() {
    try {
        const response = await fetch(`${API_BASE}/usage`);
        if (!response.ok) return;

        const usage = await response.json();

        if (usage.current_remaining !== null) {
            apiRemaining.textContent = `API Requests: ${usage.current_remaining} remaining`;
        }

        if (usage.month && usage.month.total_used_month !== null) {
            apiUsedMonth.textContent = `Used this month: ${usage.month.total_used_month}`;
        }
    } catch (error) {
        console.error('Error loading API usage:', error);
    }
}

// Handle scan button click
async function handleScan() {
    const sportKey = sportSelect.value;
    if (!sportKey) {
        showError('Please select a sport');
        return;
    }

    const minProfit = parseFloat(minProfitInput.value) / 100; // Convert to decimal

    setLoading(true);
    hideError();

    try {
        const response = await fetch(
            `${API_BASE}/scan/${sportKey}?min_profit=${minProfit}`
        );

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Scan failed');
        }

        const result = await response.json();
        displayResults(result);
        await loadApiUsage();

    } catch (error) {
        showError(error.message);
        console.error('Scan error:', error);
    } finally {
        setLoading(false);
    }
}

// Display scan results
function displayResults(result) {
    currentOpportunities = result.opportunities;

    // Update scan info
    scanInfo.style.display = 'flex';
    eventsScanned.textContent = `${result.events_scanned} events scanned`;
    opportunitiesFound.textContent = `${result.opportunities_found} opportunities found`;
    scanTime.textContent = new Date(result.scan_time).toLocaleTimeString();

    if (result.opportunities.length === 0) {
        noOpportunities.style.display = 'block';
        opportunitiesTable.style.display = 'none';
        return;
    }

    noOpportunities.style.display = 'none';
    opportunitiesTable.style.display = 'table';

    // Build table rows
    opportunitiesBody.innerHTML = '';

    result.opportunities.forEach((opp, index) => {
        const row = document.createElement('tr');

        // Get unique bookmakers
        const bookmakers = [...new Set(opp.outcomes.map(o => o.bookmaker))];

        // Format time
        const startTime = new Date(opp.commence_time);
        const timeStr = startTime.toLocaleDateString() + ' ' + startTime.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });

        row.innerHTML = `
            <td>
                <strong>${opp.away_team}</strong><br>
                <span style="color: var(--text-secondary);">@ ${opp.home_team}</span>
            </td>
            <td>${opp.sport_title}</td>
            <td class="profit-cell">${(opp.profit_margin * 100).toFixed(2)}%</td>
            <td class="bookmakers-cell">
                ${bookmakers.map(b => `<span class="bookmaker-tag">${b}</span>`).join('')}
            </td>
            <td class="time-cell">${timeStr}</td>
            <td>
                <button class="btn-secondary" onclick="showStakeCalculator(${index})">
                    Calculate Stakes
                </button>
            </td>
        `;

        opportunitiesBody.appendChild(row);
    });
}

// Show stake calculator modal
function showStakeCalculator(index) {
    selectedOpportunity = currentOpportunities[index];

    if (!selectedOpportunity) return;

    // Update modal content
    eventDetails.innerHTML = `
        <h3>${selectedOpportunity.away_team} @ ${selectedOpportunity.home_team}</h3>
        <p>${selectedOpportunity.sport_title} | Profit Margin: ${(selectedOpportunity.profit_margin * 100).toFixed(2)}%</p>
    `;

    // Use the stake from the main input
    modalStake.value = totalStakeInput.value;

    // Calculate and display stakes
    calculateAndDisplayStakes();

    // Show modal
    stakeCalculator.style.display = 'flex';
}

// Calculate and display stakes
async function calculateAndDisplayStakes() {
    if (!selectedOpportunity) return;

    const totalStake = parseFloat(modalStake.value);
    if (isNaN(totalStake) || totalStake <= 0) {
        stakeResults.innerHTML = '<p>Please enter a valid stake amount.</p>';
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/calculate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                total_stake: totalStake,
                outcomes: selectedOpportunity.outcomes,
            }),
        });

        if (!response.ok) throw new Error('Calculation failed');

        const result = await response.json();
        displayStakeResults(result);

    } catch (error) {
        stakeResults.innerHTML = '<p class="error">Failed to calculate stakes.</p>';
        console.error('Calculation error:', error);
    }
}

// Display stake calculation results
function displayStakeResults(result) {
    let html = '';

    // Individual stakes
    result.stakes.forEach(stake => {
        html += `
            <div class="stake-item">
                <div>
                    <div class="stake-outcome">${stake.outcome_name}</div>
                    <div class="stake-bookmaker">${stake.bookmaker}</div>
                </div>
                <div class="stake-amount">
                    <div class="stake-value">$${stake.stake.toFixed(2)}</div>
                    <div class="stake-odds">@ ${stake.odds.toFixed(2)}</div>
                </div>
            </div>
        `;
    });

    // Profit summary
    html += `
        <div class="profit-summary">
            <div class="profit-value">+$${result.guaranteed_profit.toFixed(2)}</div>
            <div class="profit-label">Guaranteed Profit (${result.profit_percentage.toFixed(2)}%)</div>
        </div>
    `;

    stakeResults.innerHTML = html;
}

// Recalculate stakes (called from modal)
function recalculateStakes() {
    calculateAndDisplayStakes();
}

// Close modal
function closeModal() {
    stakeCalculator.style.display = 'none';
    selectedOpportunity = null;
}

// Set loading state
function setLoading(loading) {
    scanBtn.disabled = loading;
    scanBtn.querySelector('.btn-text').style.display = loading ? 'none' : 'inline';
    scanBtn.querySelector('.btn-loading').style.display = loading ? 'inline' : 'none';
}

// Show error message
function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
}

// Hide error message
function hideError() {
    errorMessage.style.display = 'none';
}
