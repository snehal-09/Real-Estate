// ============================================================================
// EstateEase AI — frontend logic. No frameworks, just fetch() + DOM.
// ============================================================================

const state = {
  properties: [],
  sessionId: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())),
  user: { name: "", phone: "", email: "" },
  activeVisitProperty: null,
};

const money = (value) => {
  const n = Number(value) || 0;
  return "₹" + n.toLocaleString("en-IN");
};

// ----------------------------------------------------------------------------
// Property loading + rendering
// ----------------------------------------------------------------------------
async function loadProperties() {
  try {
    const res = await fetch("/api/properties");
    const data = await res.json();
    if (data.success) {
      state.properties = data.properties;
      document.getElementById("statCount").textContent = data.properties.length;
      renderProperties(data.properties, "Showing all listed properties");
    }
  } catch (err) {
    console.error("Failed to load properties", err);
  }
}

function propertyCard(p) {
  const priceLabel = p.listing_type === "Rent" ? `${money(p.price_inr)}/mo` : money(p.price_inr);
  return `
    <div class="property-card">
      <div class="property-card__media">
        <span class="property-card__tag">${p.listing_type || ""}</span>
        ${p.property_type || "Property"}
      </div>
      <div class="property-card__body">
        <div class="property-card__title">${p.title}</div>
        <div class="property-card__loc">${p.location ? p.location + ", " : ""}${p.city}</div>
        <div class="property-card__price">${priceLabel}</div>
        <div class="property-card__meta">
          <span>${p.bedrooms} BHK</span>
          <span>${p.bathrooms} Bath</span>
          <span>${p.area_sqft} sqft</span>
        </div>
        <div class="property-card__actions">
          <button class="btn btn--navy" onclick="openDetailsModal('${p.property_id}')">View Details</button>
          <button class="btn btn--gold" onclick="openVisitModal('${p.property_id}')">Schedule Visit</button>
        </div>
      </div>
    </div>
  `;
}

function renderProperties(properties, subtitle) {
  const grid = document.getElementById("propertyGrid");
  document.getElementById("resultsSubtitle").textContent = subtitle;
  if (!properties.length) {
    grid.innerHTML = `<div class="no-results">No properties matched your search. Try adjusting your filters.</div>`;
    return;
  }
  grid.innerHTML = properties.map(propertyCard).join("");
}

// ----------------------------------------------------------------------------
// Search form
// ----------------------------------------------------------------------------
document.getElementById("searchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const filters = {};
  const city = document.getElementById("f-city").value.trim();
  const location = document.getElementById("f-location").value.trim();
  const listing = document.getElementById("f-listing").value;
  const type = document.getElementById("f-type").value;
  const bedrooms = document.getElementById("f-bedrooms").value;
  const budget = document.getElementById("f-budget").value;

  if (city) filters.city = city;
  if (location) filters.location = location;
  if (listing) filters.listing_type = listing;
  if (type) filters.property_type = type;
  if (bedrooms) filters.bedrooms = Number(bedrooms);
  if (budget) filters.max_price = Number(budget);

  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(filters),
    });
    const data = await res.json();
    if (data.success) {
      renderProperties(data.properties, `${data.count} propert${data.count === 1 ? "y" : "ies"} found`);
      document.getElementById("properties").scrollIntoView({ behavior: "smooth" });
    }
  } catch (err) {
    console.error("Search failed", err);
  }
});

document.getElementById("findPropertyBtn").addEventListener("click", () => {
  document.getElementById("search").scrollIntoView({ behavior: "smooth" });
});

// ----------------------------------------------------------------------------
// Property details modal
// ----------------------------------------------------------------------------
function findProperty(id) {
  return state.properties.find((p) => p.property_id === id);
}

async function openDetailsModal(propertyId) {
  let p = findProperty(propertyId);
  if (!p) {
    try {
      const res = await fetch(`/api/properties/${propertyId}`);
      const data = await res.json();
      if (data.success) p = data.property;
    } catch (err) {
      console.error(err);
    }
  }
  if (!p) return;

  document.getElementById("detailsModalContent").innerHTML = `
    <div class="details-title">${p.title}</div>
    <div class="details-loc">${p.location ? p.location + ", " : ""}${p.city}</div>
    <div class="details-grid">
      <div><span>Property ID</span>${p.property_id}</div>
      <div><span>Listing Type</span>${p.listing_type}</div>
      <div><span>Property Type</span>${p.property_type}</div>
      <div><span>Price</span>${money(p.price_inr)}</div>
      <div><span>Bedrooms</span>${p.bedrooms}</div>
      <div><span>Bathrooms</span>${p.bathrooms}</div>
      <div><span>Area</span>${p.area_sqft} sqft</div>
      <div><span>Furnishing</span>${p.furnishing}</div>
      <div><span>Parking</span>${p.parking}</div>
      <div><span>Possession</span>${p.possession}</div>
      <div><span>Agent</span>${p.agent_name}</div>
      <div><span>Agent Phone</span>${p.agent_phone}</div>
    </div>
    <div><span style="display:block;color:#6C7688;font-size:.78rem;text-transform:uppercase;margin-bottom:6px;">Amenities</span>${p.amenities || "—"}</div>
    <div class="details-actions" style="margin-top:18px;">
      <button class="btn btn--gold" onclick="closeModal('detailsModal'); openVisitModal('${p.property_id}')">Schedule Visit</button>
      <button class="btn btn--navy" onclick="closeModal('detailsModal'); openLeadModal('${p.property_id}')">Contact Agent</button>
    </div>
  `;
  openModal("detailsModal");
}

// ----------------------------------------------------------------------------
// Modal helpers
// ----------------------------------------------------------------------------
function openModal(id) { document.getElementById(id).classList.add("is-open"); }
function closeModal(id) { document.getElementById(id).classList.remove("is-open"); }

document.querySelectorAll(".modal").forEach((modal) => {
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(modal.id); });
});
document.getElementById("detailsModalClose").addEventListener("click", () => closeModal("detailsModal"));
document.getElementById("leadModalClose").addEventListener("click", () => closeModal("leadModal"));
document.getElementById("visitModalClose").addEventListener("click", () => closeModal("visitModal"));

// ----------------------------------------------------------------------------
// Lead form
// ----------------------------------------------------------------------------
function openLeadModal(propertyId) {
  state.activeVisitProperty = propertyId || null;
  document.getElementById("leadFormStatus").textContent = "";
  openModal("leadModal");
}
document.getElementById("ctaTalkBtn").addEventListener("click", () => openLeadModal(null));

document.getElementById("leadForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("leadFormStatus");
  const name = document.getElementById("lead-name").value.trim();
  const phone = document.getElementById("lead-phone").value.trim();
  const email = document.getElementById("lead-email").value.trim();
  const requirement = document.getElementById("lead-requirement").value.trim();

  const prop = state.activeVisitProperty ? findProperty(state.activeVisitProperty) : null;

  try {
    const res = await fetch("/api/lead", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name, phone, email, requirement,
        property_id: prop ? prop.property_id : "",
        property_name: prop ? prop.title : "",
        city: prop ? prop.city : "",
        location: prop ? prop.location : "",
        listing_type: prop ? prop.listing_type : "",
        bedrooms: prop ? prop.bedrooms : "",
      }),
    });
    const data = await res.json();
    if (data.success) {
      status.textContent = "Thanks! An agent will contact you shortly.";
      status.className = "form-status success";
      e.target.reset();
      setTimeout(() => closeModal("leadModal"), 1600);
    } else {
      status.textContent = data.error || "Something went wrong. Please try again.";
      status.className = "form-status error";
    }
  } catch (err) {
    status.textContent = "Something went wrong. Please try again.";
    status.className = "form-status error";
  }
});

// ----------------------------------------------------------------------------
// Visit scheduling form
// ----------------------------------------------------------------------------
function openVisitModal(propertyId) {
  state.activeVisitProperty = propertyId;
  const p = findProperty(propertyId);
  document.getElementById("visitPropertyLabel").textContent = p ? `Scheduling a visit for: ${p.title}` : "";
  document.getElementById("visitFormStatus").textContent = "";
  openModal("visitModal");
}

document.getElementById("visitForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("visitFormStatus");
  const p = findProperty(state.activeVisitProperty);

  try {
    const res = await fetch("/api/schedule-visit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.getElementById("visit-name").value.trim(),
        phone: document.getElementById("visit-phone").value.trim(),
        email: document.getElementById("visit-email").value.trim(),
        property_id: state.activeVisitProperty || "",
        property_name: p ? p.title : "",
        preferred_date: document.getElementById("visit-date").value,
        preferred_time: document.getElementById("visit-time").value,
        customer_query: document.getElementById("visit-message").value.trim(),
      }),
    });
    const data = await res.json();
    if (data.success) {
      status.textContent = "Visit scheduled! We'll confirm with you shortly.";
      status.className = "form-status success";
      e.target.reset();
      setTimeout(() => closeModal("visitModal"), 1600);
    } else {
      status.textContent = data.error || "Something went wrong. Please try again.";
      status.className = "form-status error";
    }
  } catch (err) {
    status.textContent = "Something went wrong. Please try again.";
    status.className = "form-status error";
  }
});

// ----------------------------------------------------------------------------
// EMI Calculator
// ----------------------------------------------------------------------------
document.getElementById("emiCalcBtn").addEventListener("click", async () => {
  const loan_amount = Number(document.getElementById("emi-amount").value);
  const interest_rate = Number(document.getElementById("emi-rate").value);
  const tenure_years = Number(document.getElementById("emi-tenure").value);

  try {
    const res = await fetch("/api/emi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ loan_amount, interest_rate, tenure_years }),
    });
    const data = await res.json();
    if (res.ok) {
      document.getElementById("emiMonthly").textContent = money(data.monthly_emi);
      document.getElementById("emiInterest").textContent = money(data.total_interest);
      document.getElementById("emiTotal").textContent = money(data.total_payment);
    } else {
      alert(data.error || "Could not calculate EMI.");
    }
  } catch (err) {
    console.error(err);
  }
});

// ----------------------------------------------------------------------------
// Chatbot
// ----------------------------------------------------------------------------
const chatFab = document.getElementById("chatFab");
const chatPanel = document.getElementById("chatPanel");
const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");

function toggleChat(open) {
  chatPanel.classList.toggle("is-open", open);
  if (open) chatInput.focus();
}
chatFab.addEventListener("click", () => toggleChat(!chatPanel.classList.contains("is-open")));
document.getElementById("chatPanelClose").addEventListener("click", () => toggleChat(false));
document.getElementById("heroChatBtn").addEventListener("click", () => toggleChat(true));

function addUserMessage(text) {
  const div = document.createElement("div");
  div.className = "chat-msg chat-msg--user";
  div.innerHTML = `<p></p>`;
  div.querySelector("p").textContent = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addBotMessage(text, properties) {
  const div = document.createElement("div");
  div.className = "chat-msg chat-msg--bot";
  const p = document.createElement("p");
  p.textContent = text;
  div.appendChild(p);

  if (properties && properties.length) {
    const list = document.createElement("div");
    list.className = "chat-property-list";
    properties.slice(0, 5).forEach((prop) => {
      const item = document.createElement("div");
      item.className = "chat-property";
      const priceLabel = prop.listing_type === "Rent" ? `${money(prop.price_inr)}/mo` : money(prop.price_inr);
      item.innerHTML = `
        <strong>${prop.title}</strong>
        <div class="chat-property__meta">${prop.bedrooms} BHK · ${prop.location || ""} ${prop.city} · ${prop.area_sqft} sqft</div>
        <div class="chat-property__price">${priceLabel}</div>
        <span class="chat-property__link">View details</span>
      `;
      item.querySelector(".chat-property__link").addEventListener("click", () => openDetailsModal(prop.property_id));
      list.appendChild(item);
    });
    div.appendChild(list);
  }

  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendChatMessage(message) {
  addUserMessage(message);
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.sessionId,
        message,
        user: state.user,
      }),
    });
    const data = await res.json();
    if (data.success) {
      addBotMessage(data.message, data.properties);
      if (data.intent === "schedule_visit") {
        const lastProp = (data.properties && data.properties[0]) || state.properties[0];
        if (lastProp) openVisitModal(lastProp.property_id);
      } else if (data.intent === "lead_generation" || data.intent === "contact_agent") {
        openLeadModal(null);
      }
    } else {
      addBotMessage(data.error || "Something went wrong. Please try again.");
    }
  } catch (err) {
    addBotMessage("I'm having trouble connecting right now. Please try again in a moment.");
  }
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  chatInput.value = "";
  sendChatMessage(message);
});

document.querySelectorAll("#quickActions button").forEach((btn) => {
  btn.addEventListener("click", () => {
    toggleChat(true);
    sendChatMessage(btn.dataset.msg);
  });
});

// ----------------------------------------------------------------------------
// Mobile nav
// ----------------------------------------------------------------------------
document.getElementById("navToggle").addEventListener("click", () => {
  document.getElementById("navLinks").classList.toggle("is-open");
});

// ----------------------------------------------------------------------------
// Init
// ----------------------------------------------------------------------------
loadProperties();
