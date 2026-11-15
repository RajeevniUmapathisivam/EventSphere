const venueForm = ES.get("venue-form");
const eventForm = ES.get("event-form");
const logForm = ES.get("log-form");
const olderMessages = ES.get("older-messages");
const categoryFields = ES.get("ticket-types");
let venues = [];
let logConversation = "";
let nextMessageId = null;

function addCategory() {
    const row = document.createElement("div");
    row.className = "ticket-type fields";
    row.innerHTML = `<label>Ticket name <input name="ticket_name" required maxlength="100"></label>
        <label>Price (LKR) <input name="price" required type="number" min="0" step="0.01"></label>
        <label>Quantity <input name="quantity" required type="number" min="1" max="100000"></label>`;
    if (categoryFields.children.length) {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "secondary";
        remove.textContent = "Remove category";
        remove.onclick = () => { row.remove(); ES.get("add-category").disabled = false; };
        row.append(remove);
    }
    categoryFields.append(row);
    ES.get("add-category").disabled = categoryFields.children.length >= 20;
}

function resetVenue() {
    venueForm.reset();
    venueForm.elements.venue_id.value = "";
    ES.get("venue-submit").textContent = "Create venue";
    ES.get("venue-reset").hidden = true;
}

function renderVenues() {
    const select = eventForm.elements.venue_id;
    const current = select.value;
    select.replaceChildren(...venues.map(venue => new Option(venue.name + " · " + venue.location, venue.id)));
    if (venues.some(venue => String(venue.id) === current)) select.value = current;
    ES.get("event-submit").disabled = !venues.length;
    ES.get("venues").innerHTML = venues.map(venue => `<article class="card">
        ${ES.image({...venue, venue: venue.name})}
        <h3>${ES.escape(venue.name)}</h3>
        <p>${ES.escape(venue.location)} · capacity ${venue.capacity}</p>
        <p>${ES.money(venue.hourly_rate)} per hour · ${venue.open_for_hire ? "Open for private hire" : "Closed to private hire"}</p>
        <p>${ES.escape(venue.description)}</p>
        <button type="button" class="secondary" data-edit-venue="${venue.id}">Edit venue</button>
    </article>`).join("") || "<p>Create a venue before adding an event.</p>";
}

async function loadLog(before = null) {
    const id = before === null ? logForm.elements.conversation_id.value.trim() : logConversation;
    const params = new URLSearchParams();
    if (id) params.set("conversation_id", id);
    if (before !== null) params.set("before_id", before);
    const result = await ES.api("/admin/messages?" + params);
    const html = result.messages.map(record => `<article class="card">
        <p><strong>${ES.escape(record.performative)}</strong> · ${ES.escape(record.sender)} → ${ES.escape(record.receiver)}</p>
        <p>${ES.date(record.created_at)} · <button class="secondary" type="button" data-conversation="${ES.escape(record.conversation_id)}">${ES.escape(record.conversation_id)}</button></p>
        <pre>${ES.escape(JSON.stringify(record.content, null, 2))}</pre>
    </article>`).join("");
    const messages = ES.get("messages");
    if (before === null) messages.innerHTML = html || "<p>No messages found.</p>";
    else messages.insertAdjacentHTML("beforeend", html);
    logConversation = id;
    nextMessageId = result.next_before_id;
    olderMessages.hidden = nextMessageId === null;
}

async function load() {
    const [allVenues, events, hires] = await Promise.all([
        ES.api("/admin/venues"), ES.api("/admin/events"), ES.api("/admin/hires"),
    ]);
    venues = allVenues;
    renderVenues();
    ES.get("admin-events").innerHTML = events.map(event => `<article class="card">
        <h3>${ES.escape(event.title)}</h3>
        <p>${ES.escape(event.category)} · ${ES.escape(event.venue)}</p>
        <p>${ES.date(event.start_time)} to ${ES.date(event.end_time)}</p>
        <p class="status" data-state="${ES.escape(event.status)}">${ES.escape(event.status)}</p>
        <dl class="event-metrics">
            <div><dt>Tickets sold</dt><dd>${event.sold}</dd></div>
            <div><dt>Check-ins</dt><dd>${event.checkins}</dd></div>
            <div><dt>Net simulated revenue</dt><dd>${ES.money(event.net_revenue)}</dd></div>
            <div><dt>Venue capacity</dt><dd>${event.venue_capacity}</dd></div>
        </dl>
        <p class="helper">${event.ticket_capacity} tickets allocated</p>
        ${event.status === "draft" ? `<button data-event="${event.id}" data-action="publish">Publish</button>` : ""}
        ${event.status === "published" ? `<button class="danger" data-event="${event.id}" data-action="cancel">Cancel event</button>` : ""}
    </article>`).join("") || "<p>No events yet.</p>";
    ES.get("hires").innerHTML = hires.map(hire => `<article class="card">
        <h3>${ES.escape(hire.venue)}</h3>
        <p>${ES.date(hire.start_time)} to ${ES.date(hire.end_time)} · ${hire.guests} guests</p>
        <p>${ES.escape(hire.purpose)}</p>
        <p class="status">${ES.escape(hire.status)} · ${ES.money(hire.price)}</p>
        ${hire.status === "pending" ? `<div class="actions">
            <button data-hire="${hire.id}" data-approve="yes">Approve</button>
            <button class="danger" data-hire="${hire.id}" data-approve="no">Reject</button>
        </div>` : ""}
    </article>`).join("") || "<p>No hire requests yet.</p>";
    await loadLog();
}

ES.get("add-category").onclick = addCategory;
ES.get("venue-reset").onclick = resetVenue;
ES.click(ES.get("venues"), "edit-venue", button => {
    const selected = venues.find(venue => venue.id === Number(button.dataset.editVenue));
    venueForm.elements.venue_id.value = selected.id;
    for (const name of ["name", "location", "capacity", "hourly_rate", "image_url", "description"]) {
        venueForm.elements[name].value = selected[name] ?? "";
    }
    venueForm.elements.open_for_hire.checked = selected.open_for_hire;
    ES.get("venue-submit").textContent = "Save venue";
    ES.get("venue-reset").hidden = false;
    venueForm.elements.name.focus();
});
ES.submit(venueForm, fields => {
    const {venue_id, ...values} = Object.fromEntries(new FormData(venueForm));
    values.capacity = Number(values.capacity);
    values.image_url = values.image_url || null;
    values.open_for_hire = fields.open_for_hire.checked;
    return ES.api("/admin/venues" + (venue_id ? "/" + venue_id : ""), venue_id ? "PUT" : "POST", values).then(async () => {
        resetVenue();
        ES.notice("Venue saved.");
        await load();
    });
});
ES.submit(eventForm, async () => {
    const values = Object.fromEntries(new FormData(eventForm));
    const {title, category, venue_id, start_time, end_time, description, status} = values;
    const ticket_categories = [...categoryFields.children].map(row => ({
        name: row.querySelector('[name="ticket_name"]').value,
        price: row.querySelector('[name="price"]').value,
        quantity: Number(row.querySelector('[name="quantity"]').value),
    }));
    await ES.api("/admin/events", "POST", {
        title, category, description, status, ticket_categories, venue_id: Number(venue_id),
        start_time: new Date(start_time).toISOString(), end_time: new Date(end_time).toISOString(),
    });
    eventForm.reset();
    categoryFields.replaceChildren();
    addCategory();
    ES.notice("Event saved as " + status + ".");
    await load();
});
ES.click(ES.get("admin-events"), "event", async button => {
    const {event, action} = button.dataset;
    if (action === "cancel" && !confirm("Cancel this event and fully refund its active bookings?")) return;
    const result = await ES.api(`/admin/events/${event}/${action}`, "POST");
    ES.notice(action === "publish" ? "Event published." : `Event cancelled. Refunded ${result.refunded_bookings} bookings.`);
    await load();
});
ES.click(ES.get("hires"), "hire", async button => {
    const result = await ES.api(`/admin/hires/${button.dataset.hire}/review`, "POST", {
        approved: button.dataset.approve === "yes",
    });
    ES.notice("Hire " + result.status + ".");
    await load();
});
ES.submit(logForm, () => loadLog());
olderMessages.onclick = () => ES.run(() => loadLog(nextMessageId), olderMessages);
ES.click(ES.get("messages"), "conversation", async button => {
    logForm.elements.conversation_id.value = button.dataset.conversation;
    await loadLog();
});
addCategory();
ES.run(load);
