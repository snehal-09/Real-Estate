// ============================================================================
// EstateEase AI — Chat Widget logic.
// Talks to the SAME backend (/api/chat, /api/properties/<id>, /api/lead,
// /api/schedule-visit) as the full site did — only the frontend surface
// here is reduced to the floating button + panel + its 3 support modals.
// ============================================================================

const eeState = {
  sessionId: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())),
  user: { name: "", phone: "", email: "" },
  activeProperty: null,
  propertyCache: {},
  isSending: false,
};

const eeMoney = (value) => {
  const n = Number(value) || 0;
  return "₹" + n.toLocaleString("en-IN");
};

// ----------------------------------------------------------------------------
// Modal helpers
// ----------------------------------------------------------------------------
function eeOpenModal(id) { document.getElementById(id).classList.add("is-open"); }
function eeCloseModal(id) { document.getElementById(id).classList.remove("is-open"); }

document.querySelectorAll(".ee-modal").forEach((modal) => {
  modal.addEventListener("click", (e) => { if (e.target === modal) eeCloseModal(modal.id); });
});
document.getElementById("detailsModalClose").addEventListener("click", () => eeCloseModal("detailsModal"));
document.getElementById("leadModalClose").addEventListener("click", () => eeCloseModal("leadModal"));
document.getElementById("visitModalClose").addEventListener("click", () => eeCloseModal("visitModal"));

// ----------------------------------------------------------------------------
// Property details modal (fetched on demand via /api/properties/<id>)
// ----------------------------------------------------------------------------
async function eeOpenDetailsModal(propertyId) {
  let p = eeState.propertyCache[propertyId];
  if (!p) {
    try {
      const res = await fetch(`/api/properties/${propertyId}`);
      const data = await res.json();
      if (data.success) {
        p = data.property;
        eeState.propertyCache[propertyId] = p;
      }
    } catch (err) {
      console.error(err);
    }
  }
  if (!p) return;

  document.getElementById("detailsModalContent").innerHTML = `
    <div class="ee-details-title">${p.title}</div>
    <div class="ee-details-loc">${p.location ? p.location + ", " : ""}${p.city}</div>
    <div class="ee-details-grid">
      <div><span>Property ID</span>${p.property_id}</div>
      <div><span>Listing Type</span>${p.listing_type}</div>
      <div><span>Property Type</span>${p.property_type}</div>
      <div><span>Price</span>${eeMoney(p.price_inr)}</div>
      <div><span>Bedrooms</span>${p.bedrooms}</div>
      <div><span>Bathrooms</span>${p.bathrooms}</div>
      <div><span>Area</span>${p.area_sqft} sqft</div>
      <div><span>Furnishing</span>${p.furnishing}</div>
      <div><span>Parking</span>${p.parking}</div>
      <div><span>Possession</span>${p.possession}</div>
      <div><span>Agent</span>${p.agent_name}</div>
      <div><span>Agent Phone</span>${p.agent_phone}</div>
    </div>
    <span class="ee-amenities-label">Amenities</span>${p.amenities || "—"}
    <div class="ee-details-actions">
      <button class="ee-btn ee-btn--gold" id="detailsScheduleBtn">Schedule Visit</button>
      <button class="ee-btn ee-btn--navy" id="detailsContactBtn">Contact Agent</button>
    </div>
  `;
  document.getElementById("detailsScheduleBtn").addEventListener("click", () => {
    eeCloseModal("detailsModal");
    eeOpenVisitModal(p.property_id);
  });
  document.getElementById("detailsContactBtn").addEventListener("click", () => {
    eeCloseModal("detailsModal");
    eeOpenLeadModal(p.property_id);
  });
  eeOpenModal("detailsModal");
}

// ----------------------------------------------------------------------------
// Lead form ("talk to an agent")
// ----------------------------------------------------------------------------
function eeOpenLeadModal(propertyId) {
  eeState.activeProperty = propertyId || null;
  document.getElementById("leadFormStatus").textContent = "";
  eeOpenModal("leadModal");
}

document.getElementById("leadForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("leadFormStatus");
  const name = document.getElementById("lead-name").value.trim();
  const phone = document.getElementById("lead-phone").value.trim();
  const email = document.getElementById("lead-email").value.trim();
  const requirement = document.getElementById("lead-requirement").value.trim();
  const p = eeState.activeProperty ? eeState.propertyCache[eeState.activeProperty] : null;

  try {
    const res = await fetch("/api/lead", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name, phone, email, requirement,
        property_id: p ? p.property_id : "",
        property_name: p ? p.title : "",
        city: p ? p.city : "",
        location: p ? p.location : "",
        listing_type: p ? p.listing_type : "",
        bedrooms: p ? p.bedrooms : "",
      }),
    });
    const data = await res.json();
    if (data.success) {
      status.textContent = "Thanks! An agent will contact you shortly.";
      status.className = "ee-form-status success";
      e.target.reset();
      setTimeout(() => eeCloseModal("leadModal"), 1600);
    } else {
      status.textContent = data.error || "Something went wrong. Please try again.";
      status.className = "ee-form-status error";
    }
  } catch (err) {
    status.textContent = "Something went wrong. Please try again.";
    status.className = "ee-form-status error";
  }
});

// ----------------------------------------------------------------------------
// Visit scheduling form
// ----------------------------------------------------------------------------
function eeOpenVisitModal(propertyId) {
  eeState.activeProperty = propertyId;
  const p = eeState.propertyCache[propertyId];
  document.getElementById("visitPropertyLabel").textContent = p ? `Scheduling a visit for: ${p.title}` : "";
  document.getElementById("visitFormStatus").textContent = "";
  eeOpenModal("visitModal");
}

document.getElementById("visitForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("visitFormStatus");
  const p = eeState.propertyCache[eeState.activeProperty];

  try {
    const res = await fetch("/api/schedule-visit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.getElementById("visit-name").value.trim(),
        phone: document.getElementById("visit-phone").value.trim(),
        email: document.getElementById("visit-email").value.trim(),
        property_id: eeState.activeProperty || "",
        property_name: p ? p.title : "",
        preferred_date: document.getElementById("visit-date").value,
        preferred_time: document.getElementById("visit-time").value,
        customer_query: document.getElementById("visit-message").value.trim(),
      }),
    });
    const data = await res.json();
    if (data.success) {
      status.textContent = "Visit scheduled! We'll confirm with you shortly.";
      status.className = "ee-form-status success";
      e.target.reset();
      setTimeout(() => eeCloseModal("visitModal"), 1600);
    } else {
      status.textContent = data.error || "Something went wrong. Please try again.";
      status.className = "ee-form-status error";
    }
  } catch (err) {
    status.textContent = "Something went wrong. Please try again.";
    status.className = "ee-form-status error";
  }
});

// ----------------------------------------------------------------------------
// Chat widget
// ----------------------------------------------------------------------------
const chatFab = document.getElementById("chatFab");
const chatPanel = document.getElementById("chatPanel");
const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");

function eeToggleChat(open) {
  chatPanel.classList.toggle("is-open", open);
  chatFab.classList.toggle("is-active", open);
  if (open) chatInput.focus();
}
chatFab.addEventListener("click", () => eeToggleChat(!chatPanel.classList.contains("is-open")));
document.getElementById("chatPanelClose").addEventListener("click", () => eeToggleChat(false));

function eeAddUserMessage(text) {
  const div = document.createElement("div");
  div.className = "ee-chat-msg ee-chat-msg--user";
  const p = document.createElement("p");
  p.textContent = text;
  div.appendChild(p);
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function eeAddBotMessage(text, properties) {
  const div = document.createElement("div");
  div.className = "ee-chat-msg ee-chat-msg--bot";
  const p = document.createElement("p");
  p.textContent = text;
  div.appendChild(p);

  if (properties && properties.length) {
    const list = document.createElement("div");
    list.className = "ee-chat-property-list";
    properties.slice(0, 5).forEach((prop, idx) => {
      eeState.propertyCache[prop.property_id] = prop;
      const item = document.createElement("div");
      item.className = "ee-chat-property";
      item.style.animationDelay = `${idx * 0.05}s`;
      const priceLabel = prop.listing_type === "Rent" ? `${eeMoney(prop.price_inr)}/mo` : eeMoney(prop.price_inr);
      item.innerHTML = `
        <div class="ee-chat-property__top">
          <strong>${prop.title}</strong>
          <span class="ee-chat-property__badge">${prop.listing_type || ""}</span>
        </div>
        <div class="ee-chat-property__meta">${prop.bedrooms} BHK · ${prop.location || ""} ${prop.city} · ${prop.area_sqft} sqft</div>
        <div class="ee-chat-property__price">${priceLabel}</div>
        <span class="ee-chat-property__link">View details</span>
      `;
      item.querySelector(".ee-chat-property__link").addEventListener("click", () => eeOpenDetailsModal(prop.property_id));
      list.appendChild(item);
    });
    div.appendChild(list);
  }

  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

// ----------------------------------------------------------------------------
// Contextual follow-up chips - a small set of likely next moves, chosen from
// the intent and results Python already computed. Clicking one just sends
// that phrase through the normal chat flow, so no new backend logic needed.
// ----------------------------------------------------------------------------
function eeFollowupsForIntent(intent, data) {
  const properties = data.properties || [];
  if (intent === "property_search" || intent === "property_recommendation") {
    if (properties.length > 0) {
      return ["Which one is ready to move?", "Show me the cheapest one", "Calculate EMI for the first one", "Schedule a visit"];
    }
    return ["Increase my budget", "Try a different city", "Show 1 BHK instead"];
  }
  if (intent === "emi_calculation") {
    return ["Try a different loan amount", "Find properties in this budget", "Schedule a visit"];
  }
  if (intent === "greeting") {
    return ["2 BHK in Pune", "Properties under ₹80L", "Calculate EMI"];
  }
  if (intent === "property_details") {
    return ["Schedule a visit", "Talk to an agent", "Show similar properties"];
  }
  return [];
}

function eeAddFollowupChips(container, intent, data) {
  const suggestions = eeFollowupsForIntent(intent, data);
  if (!suggestions.length) return;

  const chipRow = document.createElement("div");
  chipRow.className = "ee-followup-chips";
  suggestions.forEach((text, idx) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "ee-followup-chip";
    chip.textContent = text;
    chip.style.animationDelay = `${idx * 0.05}s`;
    chip.addEventListener("click", () => {
      chipRow.remove();
      eeSendChatMessage(text);
    });
    chipRow.appendChild(chip);
  });
  container.appendChild(chipRow);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ----------------------------------------------------------------------------
// Typing indicator - shown while waiting for /api/chat to respond
// ----------------------------------------------------------------------------
let eeTypingEl = null;

function eeShowTyping() {
  if (eeTypingEl) return;
  eeTypingEl = document.createElement("div");
  eeTypingEl.className = "ee-chat-msg ee-chat-msg--bot ee-chat-msg--typing";
  eeTypingEl.innerHTML = `
    <p class="ee-typing-dots">
      <span></span><span></span><span></span>
    </p>
  `;
  chatMessages.appendChild(eeTypingEl);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function eeHideTyping() {
  if (eeTypingEl) {
    eeTypingEl.remove();
    eeTypingEl = null;
  }
}

async function eeSendChatMessage(message) {
  if (eeState.isSending) return;
  eeState.isSending = true;
  chatInput.disabled = true;
  eeAddUserMessage(message);
  eeShowTyping();
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: eeState.sessionId,
        message,
        user: eeState.user,
      }),
    });
    const data = await res.json();
    eeHideTyping();
    if (data.success) {
      const msgEl = eeAddBotMessage(data.message, data.properties);
      eeAddFollowupChips(msgEl, data.intent, data);
      if (data.intent === "schedule_visit") {
        const lastProp = data.properties && data.properties[0];
        if (lastProp) {
          eeState.propertyCache[lastProp.property_id] = lastProp;
          eeOpenVisitModal(lastProp.property_id);
        }
      } else if (data.intent === "lead_generation" || data.intent === "contact_agent") {
        eeOpenLeadModal(null);
      }
    } else {
      eeAddBotMessage(data.error || "Something went wrong. Please try again.");
    }
  } catch (err) {
    eeHideTyping();
    eeAddBotMessage("I'm having trouble connecting right now. Please try again in a moment.");
  } finally {
    eeState.isSending = false;
    chatInput.disabled = false;
    chatInput.focus();
  }
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  chatInput.value = "";
  eeSendChatMessage(message);
});

document.querySelectorAll("#quickActions button").forEach((btn) => {
  btn.addEventListener("click", () => {
    eeToggleChat(true);
    eeSendChatMessage(btn.dataset.msg);
  });
});